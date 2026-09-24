from command_result import CommandResult
from index_command import IndexCommand

DEFAULT_MAX_TEXTS = 1


class Rare(IndexCommand):
  """Narrows the active pool to the words the library rarely uses."""

  @staticmethod
  def cmd_name():
    return 'rare'

  def overview(self):
    return 'rare [n]: keep the active pool\'s words that are in at most n books (default 1)'

  def matches(self, line):
    return self.check_match(r'rare( \d+)?', line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  # This filters the active pool rather than querying the library, which is
  # what makes it compose: the pool it narrows can be a book, a saved pool,
  # or the result of a set operation, and the answer means the same thing
  # each time.
  #
  # It is also the honest version of what `rd` approximates. `rd` subtracts a
  # frequency list, so a word is unusual when a lexicographer left it out;
  # here a word is unusual when this library's own books do not use it.
  def execute(self, args_, context):
    words = context.get('words')
    if not words:
      return CommandResult.fail('No words are loaded. Use load, r or dr first.')

    max_texts = int(args_[0]) if args_ else DEFAULT_MAX_TEXTS
    if max_texts < 1:
      return CommandResult.fail('Ask for words in at least one book.')

    if not self.ready():
      return CommandResult.fail(self.not_ready_message())

    kept = self.index.filter_rare(words, max_texts)
    if not kept:
      # Refusing beats storing an empty pool: the next draw would fail with
      # a message about loading a file, which is not what went wrong.
      return CommandResult.fail(
          f'None of those {len(words):,} words are in {max_texts} book(s) '
          f'or fewer; keeping the current pool.')

    books = 'one book' if max_texts == 1 else f'at most {max_texts} books'
    active_counts = getattr(context, 'counts', {}).get('words', {})
    counts = {w: active_counts.get(w, 1) for w in kept}
    tokens = sum(counts.values())
    return CommandResult(
        message=f'{len(kept):,} of {len(words):,} words are in {books}.',
        updates={'words': kept},
        counts={'words': counts},
        data={'size': len(kept), 'from': len(words), 'max_texts': max_texts})
