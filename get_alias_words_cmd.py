import logging
import random

from command import Command
from arg import Arg

logger = logging.getLogger(__name__)

class GetAliasWords(Command):

  @staticmethod
  def cmd_name():
    return 'get_alias_words'

  @staticmethod
  def cmd_args():
    return [Arg(str, repeated=True)]

  def overview(self):
    return 'get_alias_words [gaw] (alias, rand)+'

  def matches(self, line):
    regex = r'(get_alias_words|gaw)( \w+)+'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    keys = []
    print_choices = False
    for arg in args_:
      if arg in ['r', 'rand', 'random']:
        choices = list(context.keys())
        try:
          choices.remove('words')
        except ValueError:
          pass # Word not in list, probably test
        arg = random.choice(list(choices))
        print_choices = True
      if arg not in context:
        print(f"Arg {arg} was not found in context! Valid values are {list(context.keys())}.")
        return None
      keys.append(arg)
    output = ''
    for arg in keys:
      output += random.choice(context[arg])
      output += ' '
    if print_choices:
      output += '['
      for key in keys:
        output += key
        output += ' '
    # Strip final space.
    output = output[:-1]
    if print_choices:
      output += ']'
    print(output)
