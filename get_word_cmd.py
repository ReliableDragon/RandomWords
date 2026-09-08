import random

from command import Command
from command_result import CommandResult

class GetWord(Command):

  @staticmethod
  def cmd_name():
    return 'get_word'

  def overview(self):
    return 'get_word: "word", "next", a number, or an empty line'

  def matches(self, line):
    line = line.strip().lower()
    if line in ['', 'word', 'next']:
      return True
    if line.isnumeric():
      return True
    return False

  def parse_args(self, line):
    line = line.strip()
    if line.isnumeric():
      return [int(line)]
    return []

  def execute(self, args_, context):
    words = context.get('words')
    if not words:
      return CommandResult.fail('No words are loaded. Use load, r or dr first.')
    num = args_[0] if args_ else 1
    # random.sample draws without replacement, so a multi-word draw never
    # repeats a word while the pool is big enough to cover it. Once the pool
    # is smaller than the request, sample can't satisfy it (it raises), so we
    # fall back to sampling with replacement, which is the only way left to
    # hand back exactly the number of words asked for.
    if num <= len(words):
      drawn = random.sample(words, num)
    else:
      drawn = [random.choice(words) for _ in range(num)]
    return CommandResult(message=' '.join(drawn), data={'drawn': drawn})
