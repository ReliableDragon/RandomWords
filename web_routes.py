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
  vault: object = None
  world_index: object = None
  word_index: object = None


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


# Records where the active pool came from when a command replaced it.
#
# The named routes do this for themselves, but the command language reaches
# the same commands without passing through them, and a `load` typed there
# left the page naming the pool it had replaced. Only a command that reports
# a source updates the label: `rare` narrows a book without changing which
# book it is, so it leaves the name alone rather than clearing it.
def note_loaded_pool(session, result: CommandResult) -> None:
  if not result.ok or result.confirm or 'words' not in result.updates:
    return
  source = (result.data or {}).get('source')
  if source:
    session.note_source('words', session.sources.get(source, source))


def fail(status: int, message: str) -> Response:
  return Response(status, {'ok': False, 'message': message})


# Applies updates a command withheld pending a confirmation, once the
# request has brought back a yes as `force`. Shared by every route whose
# command can carry a `confirm` -- saving, combining, writing, and the raw
# command line -- so the same lines are not retyped a fourth time.
#
# The result `apply` hands back, not the one passed in, is what gets
# returned: for most commands they are the same object, because merging
# `updates` cannot fail. `write`'s command is the exception -- its
# `on_confirm` callback can raise if the disk write itself fails -- and
# using apply's own answer is what lets that failure reach the response
# instead of being silently reported as a success.
def apply_if_forced(req: Request, result: CommandResult) -> CommandResult:
  if result.confirm and req.body.get('force'):
    applied = req.session.apply(result)
    return replace(applied, confirm='')
  return result


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
  result = apply_if_forced(req, result)

  note_saved_pool(req.session, result)
  return from_result(result, {'pools': req.session.pools()})


# Writes a pool to disk, under sources/custom/, so it survives a restart.
#
# An existing file comes back as a question, the same shape `save` uses for
# an existing alias; the client answers by repeating the request with
# force, which is the same yes the terminal gets from a prompt.
def write(req: Request) -> Response:
  name = req.body.get('name')
  if not isinstance(name, str) or not name:
    return fail(400, 'What should the file be called?')

  pool = req.body.get('pool')
  args = [name]
  if isinstance(pool, str) and pool:
    args.append(pool)

  result = req.session.run('save', args)
  result = apply_if_forced(req, result)
  return from_result(result, {'pools': req.session.pools()})


def forget(req: Request) -> Response:
  name = req.body.get('name')
  if not isinstance(name, str) or not name:
    return fail(400, 'Which pool should I forget?')
  result = req.session.run('forget', [name])
  return from_result(result, {'pools': req.session.pools()})


# Union, difference or intersection of two or more sources into one pool.
#
# A source may be a saved pool name or a raw library path -- the underlying
# command resolves either, so a text needs no alias step first. `sources`
# is the current way to ask for this; `a`/`b` still work for a plain
# two-pool combine.
#
# An `out` that already names a pool other than the first source comes back
# as a question rather than being overwritten, the same as `save`. `out` is
# always resolved before the command runs (defaulting to the first source)
# so the command always sees the unambiguous "sources..., out" shape,
# rather than leaning on the two-argument form's implicit "no out" meaning.
def combine(req: Request) -> Response:
  operation = req.body.get('op')
  if operation not in OPERATIONS:
    return fail(400, f'Unknown operation: {operation!r}. '
                     f'Use union, difference or intersection.')

  raw_sources = req.body.get('sources')
  if isinstance(raw_sources, list):
    names = [s for s in raw_sources if isinstance(s, str) and s]
  else:
    names = [s for s in (req.body.get('a'), req.body.get('b'))
             if isinstance(s, str) and s]
  if len(names) < 2:
    return fail(400, 'Give at least two pools to combine.')

  out = req.body.get('out')
  out = out if isinstance(out, str) and out else names[0]

  result = req.session.run(OPERATIONS[operation], names + [out])
  result = apply_if_forced(req, result)
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

  weighted = req.body.get('weighted')
  if weighted is None:
    weighted = (getattr(req.session, 'sampling_mode', 'uniform') == 'weighted')

  cmd_name = 'weighted_word' if weighted else 'get_word'
  result = req.session.run(cmd_name, [count])
  return from_result(result)


def multi_draw(req: Request) -> Response:
  """Draw one word from every requested pool, text, or folder.

  This deliberately uses the command behind ``mul`` rather than loading each
  source into the active pool.  A multi-draw is a read-only convenience: it
  must leave the active pool exactly as it was before the request.
  """
  sources = req.body.get('sources')
  if not isinstance(sources, list) or not sources:
    return fail(400, 'Give one or more sources to draw from.')
  if len(sources) > MAX_DRAW:
    return fail(400, f'Draw from at most {MAX_DRAW} sources at once.')
  if any(not isinstance(source, str) or not source for source in sources):
    return fail(400, 'Every draw source must be a nonempty string.')

  result = req.session.run('multi_folder_get_words', sources)
  return from_result(result)


def mode(req: Request) -> Response:
  if req.method == 'GET':
    return Response(200, {'ok': True, 'mode': getattr(req.session, 'sampling_mode', 'uniform')})
  new_mode = req.body.get('mode')
  if not new_mode:
    return fail(400, 'Specify a mode ("uniform" or "weighted").')
  result = req.session.run('mode', [new_mode])
  return from_result(result)


# The command language, for anything without a button yet. Reachable only on
# loopback and only behind the origin checks in web_server.py, because its
# input is a language rather than a set of named fields.
def command(req: Request) -> Response:
  line = req.body.get('line')
  if not isinstance(line, str):
    return fail(400, 'What command should I run?')

  result = req.session.run_line(line)
  result = apply_if_forced(req, result)

  if result.quit:
    # There is no session here to end, and a quit must never reach the
    # process that is serving other requests.
    return fail(400, 'There is no session to quit here. Close the tab.')

  note_saved_pool(req.session, result)
  note_loaded_pool(req.session, result)
  return from_result(result, {'pools': req.session.pools()})


def status(req: Request) -> Response:
  return Response(200, {'ok': True, 'cache': req.fm.stats(),
                        'pools': req.session.pools(),
                        'mode': getattr(req.session, 'sampling_mode', 'uniform')})


ROUTES = {
  ('GET', '/api/library'): library,
  ('GET', '/api/pools'): pools,
  ('GET', '/api/status'): status,
  ('GET', '/api/mode'): mode,
  ('POST', '/api/mode'): mode,
  ('POST', '/api/pools/load'): load,
  ('POST', '/api/pools/random'): load_random,
  ('POST', '/api/pools/save'): save,
  ('POST', '/api/pools/write'): write,
  ('POST', '/api/pools/op'): combine,
  ('POST', '/api/draw'): draw,
  ('POST', '/api/draw/multi'): multi_draw,
  ('POST', '/api/command'): command,
}


POOL_PREFIX = '/api/pools/'


# Runs a request through its route, turning the two path errors into
# ordinary failed responses so no handler has to guard for them.
def dispatch(req: Request) -> Response:
  if req.path.startswith('/api/world/'):
    if req.vault is None:
      return fail(404, f'No such endpoint: {req.method} {req.path}')
    import world_routes
    return world_routes.dispatch(req)

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
