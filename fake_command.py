from arg import Arg
from command import Command
from command_result import CommandResult

class FakeCommand(Command):

  def __init__(self):
    super().__init__()

  @staticmethod
  def cmd_name():
    return 'FakeCommand'

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(int, optional=True)]

  def execute(self, args_, context):
    super().validate_args(args_)

    str_arg = args_[0]
    int_arg = 1
    if len(args_) == 2:
      int_arg = args_[1]
    return CommandResult(message=str_arg * int_arg, updates={'test_key': 24601})
