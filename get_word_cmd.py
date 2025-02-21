import random

from command import Command

class GetWord(Command):

  @staticmethod
  def cmd_name():
    return 'get_word'

  @staticmethod
  def cmd_args():
    return []

  def matches(self, line):
    if line in ['', 'word', 'next']:
      return True
    return False

  def execute(self, args_, context):
    result = random.choice(context['words'])
    print(result)
