import logging
import os

import file_manager

from arg import Arg
from command import Command
from command_result import CommandResult

logger = logging.getLogger(__name__)

class RandDiff(Command):

  def __init__(self, command_list):
    super().__init__()
    self.command_list = command_list

  @staticmethod
  def cmd_name():
    return 'rand_diff'

  @staticmethod
  def cmd_args():
    return [Arg(str, optional=True)]

  def overview(self):
    return 'rand_diff [rd] [10|70|450]'

  def matches(self, line):
    regex = r'(rand_diff|rd)( (10|70|450))?'
    return self.check_match(regex, line)

  # Loads a random file and subtracts a common-words dictionary from it,
  # leaving only that book's unusual words as the active pool.
  def execute(self, args_, context):
    super().validate_args(args_)
    to_diff = args_[0] if args_ else '70'
    dict_path = os.path.join(file_manager.ROOT_DIR, f'dicts/{to_diff}k_words.txt')

    loaded = self.command_list.get_cmd('load_rand_file').execute([], context)
    if not loaded.ok or not loaded.updates.get('words'):
      return loaded

    # Diff the file that was just loaded, not the pool that preceded it.
    scratch = context | loaded.updates
    result = self.command_list.get_cmd('diff').execute([dict_path], scratch)

    # This command runs two others without a front end between them, so the
    # inner load's message has nowhere to go unless it is carried out here.
    messages = [m for m in (loaded.message, result.message) if m]
    return CommandResult(ok=result.ok,
                         message='\n'.join(messages),
                         data=result.data,
                         updates=result.updates)
