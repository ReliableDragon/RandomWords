from command import Command
from command_result import CommandResult

ACTIVE_POOL = 'words'

class Forget(Command):

  @staticmethod
  def cmd_name():
    return 'forget'

  def overview(self):
    return 'forget [rm] <alias>'

  def matches(self, line):
    return self.check_match(r'(forget|rm) [\w_]+', line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  def execute(self, args_, context):
    name = args_[0]

    if name == ACTIVE_POOL:
      return CommandResult.fail(
          'The active pool cannot be forgotten. Load something else instead.')
    if name not in context:
      return CommandResult.fail(
          f'There is no pool called {name}. Known names: {list(context.keys())}.')

    return CommandResult(message=f'Forgot {name}.', removes=[name],
                         data={'pool': name})
