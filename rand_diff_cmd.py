import logging

from arg import Arg
from command import Command

logger = logging.getLogger(__name__)

# TODO: Test. Probably requires allowing arbitrary
# files in the argument.
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

  def matches(self, line):
    regex = r'(rand_diff|rd)( (10|70|450))?'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    super().validate_args(args_)
    to_diff = 70
    if args_:
      to_diff = args_[0]

    diff_fname = f'dicts/{to_diff}k_words.txt'

    words = self.command_list.cmds['load_rand_file'].execute([], context)
    words = self.command_list.cmds['diff'].execute([diff_fname], context)
    
    return context

