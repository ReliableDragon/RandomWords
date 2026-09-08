from arg import Arg
from command_result import CommandResult
from index_command import IndexCommand

DEFAULT_COUNT = 10
MAX_COUNT = 100


class Like(IndexCommand):
  """The words that turn up in the same books as a given word."""

  @staticmethod
  def cmd_name():
    return 'like'

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(str, optional=True)]

  def overview(self):
    return 'like <word> [n]: words that appear in the same books'

  def matches(self, line):
    return self.check_match(r"like [\w'’-]+( \d+)?", line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  # Similarity here is Jaccard overlap of the sets of books two words appear
  # in. It is not a thesaurus and does not claim to be: `ambergris` answers
  # with `spermaceti`, `civet` and `copal` because whaling and perfumery
  # books are where all four turn up, which is the useful kind of related
  # for a tool that exists to hand you a word you had forgotten.
  def execute(self, args_, context):
    if not self.ready():
      return CommandResult.fail(self.not_ready_message())

    word = args_[0].lower()
    count = int(args_[1]) if len(args_) > 1 else DEFAULT_COUNT
    if count < 1:
      return CommandResult.fail('Ask for at least one word.')
    count = min(count, MAX_COUNT)

    seen_in = self.index.doc_count(word)
    if not seen_in:
      return CommandResult.fail(f'No book in the library uses "{word}".')
    if self.index.too_common(word):
      # Every common word shares its books with every other common word, so
      # the ranking would be a list of the commonest words in the library
      # and would say nothing about the one that was asked for.
      return CommandResult.fail(
          f'"{word}" is in {seen_in} books, which is too many to be '
          f'distinctive. Try a rarer word.')

    scored = self.index.neighbours(word, count)
    if not scored:
      return CommandResult.fail(f'Nothing else keeps company with "{word}".')

    words = [w for w, _ in scored]
    return CommandResult(message=' '.join(words),
                         data={'word': word, 'drawn': words,
                               'scores': [round(s, 3) for _, s in scored]})
