from command import Command
from command_result import CommandResult

class FakeCommand(Command):
  """A minimal stand-in for tests that need a working command without
  wiring up a real one. Its syntax is a required first argument and an
  optional second one, mirroring the shape most real commands take, and its
  execute() does just enough -- multiply the first argument by the second,
  or by 1 -- to exercise both a normal result and a command that raises."""

  def __init__(self):
    super().__init__()

  @staticmethod
  def cmd_name():
    return 'FakeCommand'

  def overview(self):
    return f'{self.name} <str> [int]'

  def matches(self, line):
    return self.check_match(rf'{self.name} [^ ]+( [^ ]+)?', line)

  def execute(self, args_, context):
    str_arg = args_[0]
    if not isinstance(str_arg, str):
      raise ValueError(f'FakeCommand expected a str first argument, got {str_arg!r}.')
    int_arg = args_[1] if len(args_) == 2 else 1
    return CommandResult(message=str_arg * int_arg, updates={'test_key': 24601})
