from command import Command
from command_result import CommandResult
from arg import Arg

class Dump(Command):

  @staticmethod
  def cmd_name():
    return 'dump'

  @staticmethod
  def cmd_args():
    return [Arg(str, optional=True)]

  def overview(self):
    return 'dump [all]'

  def execute(self, args_, context):
    if args_ and args_[0].lower() in ['all', 'full']:
      return CommandResult(message=f'context: {context}')
    if not context:
      return CommandResult(message='Nothing is loaded.')
    lines = []
    pools = []
    for name, words in context.items():
      label = 'words (active pool)' if name == 'words' else name
      lines.append(f'{label}: {len(words)} words')
      pools.append({'name': name, 'size': len(words)})
    return CommandResult(message='\n'.join(lines), data={'pools': pools})
