from command import Command
from command_result import CommandResult


class Mode(Command):

  @staticmethod
  def cmd_name():
    return 'mode'

  def overview(self):
    return 'mode [uniform|weighted]: view or set sampling mode (current: uniform)'

  def matches(self, line):
    return self.check_match(r'(mode|sampling)( (uniform|weighted|flat|occurrence))?', line)

  def parse_args(self, line):
    parts = line.strip().split()
    if len(parts) > 1:
      return [parts[1].lower()]
    return []

  def execute(self, args_, context):
    if not args_:
      current = getattr(context, 'sampling_mode', 'uniform')
      return CommandResult(message=f'Sampling mode is {current}.', data={'mode': current})

    new_mode = args_[0]
    if new_mode in ['uniform', 'flat']:
      mode = 'uniform'
    elif new_mode in ['weighted', 'occurrence']:
      mode = 'weighted'
    else:
      return CommandResult.fail(f'Unknown mode: {new_mode}. Use "mode uniform" or "mode weighted".')

    if hasattr(context, 'sampling_mode'):
      context.sampling_mode = mode
    return CommandResult(message=f'Sampling mode set to {mode}.', data={'mode': mode})
