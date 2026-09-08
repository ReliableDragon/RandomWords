from command_result import CommandResult
from index_command import IndexCommand

# Enough to see the shape of an answer without turning a draw into a page.
SHOWN = 8


class Which(IndexCommand):
  """Which books use a word."""

  @staticmethod
  def cmd_name():
    return 'which'

  def overview(self):
    return 'which <word>: the books that use a word'

  def matches(self, line):
    return self.check_match(r"which [\w'’-]+", line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  def execute(self, args_, context):
    if not self.ready():
      return CommandResult.fail(self.not_ready_message())

    word = args_[0].lower()
    texts = self.index.texts_for(word)
    total = self.index.stats()['texts']

    if not texts:
      # Silence here would be ambiguous: a word can be missing because the
      # library never uses it, or because it is only in a word list, which
      # the index does not count.
      return CommandResult(message=f'No book in the library uses "{word}".',
                           data={'word': word, 'count': 0, 'texts': []})

    shown = texts[:SHOWN]
    listing = ', '.join(shown)
    if len(texts) > SHOWN:
      listing += f', and {len(texts) - SHOWN} more'
    return CommandResult(
        message=f'"{word}" is in {len(texts)} of {total} books: {listing}',
        data={'word': word, 'count': len(texts), 'texts': texts})
