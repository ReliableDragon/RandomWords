import logging
import random

from command import Command
from command_result import CommandResult

logger = logging.getLogger(__name__)

RANDOM_ALIASES = ['r', 'rand', 'random']

class GetAliasWords(Command):

  @staticmethod
  def cmd_name():
    return 'get_alias_words'

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
          return CommandResult.fail('No aliases are defined yet. Save one with "al <name>".')
        arg = random.choice(choices)
        print_choices = True
      if arg not in context:
        return CommandResult.fail(f"Arg {arg} was not found in context! Valid values are {list(context.keys())}.")
      keys.append(arg)

    words = []
    for key in keys:
      if not context[key]:
        return CommandResult.fail(f'Alias {key} is empty.')
      words.append(random.choice(context[key]))

    output = ' '.join(words)
    if print_choices:
      output += ' [' + ' '.join(keys) + ']'
    return CommandResult(message=output, data={'drawn': words, 'aliases': keys})
