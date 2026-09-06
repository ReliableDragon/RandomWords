import logging
import random

from command import Command
from arg import Arg

logger = logging.getLogger(__name__)

RANDOM_ALIASES = ['r', 'rand', 'random']

class GetAliasWords(Command):

  @staticmethod
  def cmd_name():
    return 'get_alias_words'

  @staticmethod
  def cmd_args():
    return [Arg(str, repeated=True)]

  def overview(self):
    return 'get_alias_words [gaw] {alias or r}+'

  def matches(self, line):
    regex = r'(get_alias_words|gaw)( \w+)+'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    keys = []
    print_choices = False
    for arg in args_:
      if arg in RANDOM_ALIASES:
        # 'words' is the active pool, not a saved alias.
        choices = [key for key in context.keys() if key != 'words']
        if not choices:
          print('No aliases are defined yet. Save one with "al <name>".')
          return None
        arg = random.choice(choices)
        print_choices = True
      if arg not in context:
        print(f"Arg {arg} was not found in context! Valid values are {list(context.keys())}.")
        return None
      keys.append(arg)

    words = []
    for key in keys:
      if not context[key]:
        print(f'Alias {key} is empty.')
        return None
      words.append(random.choice(context[key]))

    output = ' '.join(words)
    if print_choices:
      output += ' [' + ' '.join(keys) + ']'
    print(output)
