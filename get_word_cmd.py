import random

from command import Command
from arg import Arg

class GetWord(Command):

  @staticmethod
  def cmd_name():
    return 'get_word'

  @staticmethod
  def cmd_args():
    return [Arg(int, optional=True)]

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
      print('No words are loaded. Use load, r or dr first.')
      return None
    num = args_[0] if args_ else 1
    print(' '.join(random.choice(words) for _ in range(num)))
