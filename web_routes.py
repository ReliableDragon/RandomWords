import logging

from dataclasses import dataclass, field, replace

from command_result import CommandResult
from file_manager import InvalidPath, UnreadableSource

# The names the API uses for the set operations. The command language spells
# them differently; this is the one place the two vocabularies meet.
OPERATIONS = {
  'union': 'combine',
  'difference': 'diff',
  'intersection': 'intersection',
}

logger = logging.getLogger(__name__)

# Caps from the security section of the design. Cheap to add now, awkward to
# retrofit.
MAX_DRAW = 1000


@dataclass
class Request():
  method: str
  path: str
  query: dict = field(default_factory=dict)
  body: dict = field(default_factory=dict)
  session: object = None
  fm: object = None


@dataclass
class Response():
  status: int
  payload: dict


# Turns a command's result into an HTTP response.
#
# The status is a function of `ok` and `confirm` and nothing else. There is
# deliberately no 404: a CommandResult carries one flag, and inventing an
# error taxonomy so a status code can be more specific is the wrong trade.
def from_result(result: CommandResult, extra: dict = None) -> Response:
  payload = {'ok': result.ok, 'message': result.message}
  if result.data:
    payload['data'] = result.data
  if extra:
    payload.update(extra)

  if result.confirm:
    payload['confirm'] = result.confirm
    return Response(409, payload)
  return Response(200 if result.ok else 400, payload)


# Records where a newly saved pool came from, whichever route saved it.
#
# A pool saved from a text names that text; one saved from the active pool
# inherits whatever the active pool came from. A pool produced by a set
# operation is derived from two others and names neither.
def note_saved_pool(session, result: CommandResult) -> None:
  data = result.data or {}
  if 'saved_from' not in data or not result.ok or result.confirm:
    return
  session.note_source(data['pool'],
                      data['saved_from'] or session.sources.get('words'))


def fail(status: int, message: str) -> Response:
  return Response(status, {'ok': False, 'message': message})


###
### Routes
###

# Folders and texts at a library path. Word counts are reported only for
# files already parsed, because counting the rest would mean reading 142 MB
# to draw a sidebar.
def library(req: Request) -> Response:
  path = req.query.get('path', '')
  result = req.session.run('ls', [path])
  if not result.ok:
    return from_result(result)

  entries = []
  for entry in result.data['entries']:
    item = dict(entry)
    if entry['is_dir']:
      item['texts'] = len(req.fm.get_txts(entry['path']))
    else:
      item['size'] = req.fm.cached_size(entry['path'])
    entries.append(item)

  return Response(200, {'ok': True, 'message': result.message,
                        'path': path, 'entries': entries})


def pools(req: Request) -> Response:
  return Response(200, {'ok': True, 'pools': req.session.pools()})


def load(req: Request) -> Response:
  source = req.body.get('source')
  if not isinstance(source, str) or not source:
    return fail(400, 'Which text should I load?')
  result = req.session.run('load', [source])
  if result.ok:
    # Copying a saved pool inherits that pool's source rather than naming
    # itself as one.
    req.session.note_source('words', req.session.sources.get(source, source))
  return from_result(result, {'pools': req.session.pools()})


def load_random(req: Request) -> Response:
  under = req.body.get('under', '')
  mode = req.body.get('mode', 'flat')
  if mode not in ('flat', 'walk'):
    return fail(400, f'Unknown mode: {mode}. Use flat or walk.')
  if not isinstance(under, str):
    return fail(400, 'Which folder should I look in?')

  if mode == 'walk':
    result = req.session.run('load_rand_dir_file', [])
  else:
    result = req.session.run('load_rand_file', [under] if under else [])
  if result.ok and result.data:
    req.session.note_source('words', result.data.get('source'))
  return from_result(result, {'pools': req.session.pools()})


# Saves the active pool, or a text, under a name.
#
# An existing name comes back as a question rather than being overwritten.
# The client answers by repeating the request with force, which is the same
# yes the terminal gets from a prompt.
def save(req: Request) -> Response:
  name = req.body.get('name')
  if not isinstance(name, str) or not name:
    return fail(400, 'What should the pool be called?')

  source = req.body.get('from')
  args = [name]
  if isinstance(source, str) and source:
    args.append(source)

  result = req.session.run('alias_load', args)

  if result.confirm and req.body.get('force'):
    req.session.apply(result)
    result = replace(result, confirm='')

  note_saved_pool(req.session, result)
  return from_result(result, {'pools': req.session.pools()})


def forget(req: Request) -> Response:
  name = req.body.get('name')
  if not isinstance(name, str) or not name:
    return fail(400, 'Which pool should I forget?')
  result = req.session.run('forget', [name])
  return from_result(result, {'pools': req.session.pools()})


# Union, difference or intersection of two pools into a third.
def combine(req: Request) -> Response:
  operation = req.body.get('op')
  if operation not in OPERATIONS:
    return fail(400, f'Unknown operation: {operation!r}. '
                     f'Use union, difference or intersection.')

  first = req.body.get('a')
  second = req.body.get('b')
  if not (isinstance(first, str) and first
          and isinstance(second, str) and second):
    return fail(400, 'Give two pools to combine.')

  args = [first, second]
  out = req.body.get('out')
  if isinstance(out, str) and out:
    args.append(out)

  result = req.session.run(OPERATIONS[operation], args)
  return from_result(result, {'pools': req.session.pools()})


def draw(req: Request) -> Response:
  count = req.body.get('count', 1)
  try:
    count = int(count)
  except (TypeError, ValueError):
    return fail(400, f'How many words? {count!r} is not a number.')
  if count < 1:
    return fail(400, 'Ask for at least one word.')
  count = min(count, MAX_DRAW)

  result = req.session.run('get_word', [count])
  return from_result(result)


# The command language, for anything without a button yet. Reachable only on
# loopback and only behind the origin checks in web_server.py, because its
# input is a language rather than a set of named fields.
def command(req: Request) -> Response:
  line = req.body.get('line')
  if not isinstance(line, str):
    return fail(400, 'What command should I run?')

  result = req.session.run_line(line)

  if result.confirm and req.body.get('force'):
    req.session.apply(result)
    result = replace(result, confirm='')

  if result.quit:
    # There is no session here to end, and a quit must never reach the
    # process that is serving other requests.
    return fail(400, 'There is no session to quit here. Close the tab.')

  note_saved_pool(req.session, result)
  return from_result(result, {'pools': req.session.pools()})


def status(req: Request) -> Response:
  return Response(200, {'ok': True, 'cache': req.fm.stats(),
                        'pools': req.session.pools()})


ROUTES = {
  ('GET', '/api/library'): library,
  ('GET', '/api/pools'): pools,
  ('GET', '/api/status'): status,
  ('POST', '/api/pools/load'): load,
  ('POST', '/api/pools/random'): load_random,
  ('POST', '/api/pools/save'): save,
  ('POST', '/api/pools/op'): combine,
  ('POST', '/api/draw'): draw,
  ('POST', '/api/command'): command,
}


POOL_PREFIX = '/api/pools/'


# Runs a request through its route, turning the two path errors into
# ordinary failed responses so no handler has to guard for them.
def dispatch(req: Request) -> Response:
  handler = ROUTES.get((req.method, req.path))

  # The one route with a name in its path.
  if handler is None and req.method == 'DELETE' and req.path.startswith(POOL_PREFIX):
    req.body = dict(req.body, name=req.path[len(POOL_PREFIX):])
    handler = forget

  if handler is None:
    return fail(404, f'No such endpoint: {req.method} {req.path}')
  try:
    return handler(req)
  except (InvalidPath, UnreadableSource) as e:
    return fail(400, str(e))
