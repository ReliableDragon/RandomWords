import random

from command import Command
from arg import Arg

class GetAliasWords(Command):

  @staticmethod
  def cmd_name():
    return 'get_alias_words'

  @staticmethod
  def cmd_args():
    return [Arg(str, repeated=True)]

  def matches(self, line):
    regex = r'(get_alias_words|gaw)( \w+)+'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    for arg in args_:
      assert arg in context, f"Arg {arg} was not found in context! Valid values are {context}"
    output = ''
    for arg in args_:
      output += random.choice(context[arg])
      output += ' '
    # Strip final space.
    output = output[:-1]
    print(output)
