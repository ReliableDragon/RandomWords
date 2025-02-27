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

  def matches(self, line):
    if line in ['', 'word', 'next']:
      return True
    if line.isnumeric():
      return True
    return False

  def parse_args(self, line):
    if line.isnumeric():
      return [int(line)]
    return []

  def execute(self, args_, context):
    result = ''
    num = 1
    if args_:
      num = args_[0]
    for _ in range(num):
      result += random.choice(context['words'])
      result += ' '
    # Remove trailing space
    result = result[:-1]
    print(result)
