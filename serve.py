import argparse
import logging
import threading

from web_server import make_server

DEFAULT_PORT = 8100
DEFAULT_WORDS = 'dicts/70k_words.txt'


# The dictionaries are the common operands and the slowest things to read, so
# they are warmed before the first request. The books are warmed behind them,
# because forty seconds of startup would be a bad trade but six is not.
#
# The index reads the same books, so it goes on the end of that same thread
# rather than beside it: two threads parsing the same file would each pay
# for it in full. After the first run it is read back from disk in
# twenty milliseconds and this costs nothing.
def warm(fm, index=None, dictionaries=True, books=True):
  dicts = [p for p in fm.get_txts('dicts')]
  if dictionaries:
    fm.warm(dicts)
  if not books:
    return None

  rest = [p for p in fm.get_txts() if p not in set(dicts)]

  def read_then_index():
    fm.warm(rest)
    if index is not None:
      index.ensure_ready()

  thread = threading.Thread(target=read_then_index, name='warm', daemon=True)
  thread.start()
  return thread


def main():
  parser = argparse.ArgumentParser(description='Serve RandomWords in a browser.')
  parser.add_argument('--port', type=int, default=DEFAULT_PORT)
  parser.add_argument('--words', default=DEFAULT_WORDS,
                      help='pool to load at startup')
  parser.add_argument('--no-warm', action='store_true',
                      help='skip reading the dictionaries before serving')
  args = parser.parse_args()

  logging.basicConfig(level=logging.WARNING)
  server = make_server(port=args.port)

  if not args.no_warm:
    print('Reading the dictionaries...')
    warm(server.fm, server.index)

  session = server.sessions.for_request()
  result = session.run('load', [args.words])
  if result.ok:
    # This load bypasses the routes, so it has to record its own source or
    # the page cannot name the startup pool.
    session.note_source('words', args.words)
  else:
    print(result.message)

  port = server.server_port
  print(f'RandomWords is at http://127.0.0.1:{port}  (ctrl-c to stop)')
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print()
  finally:
    server.shutdown()
    server.server_close()


if __name__ == '__main__':
  main()
