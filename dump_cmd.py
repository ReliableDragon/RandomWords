from command import Command
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
      print(f'context: {context}')
      return
    if not context:
      print('Nothing is loaded.')
      return
    for name, words in context.items():
      label = 'words (active pool)' if name == 'words' else name
      print(f'{label}: {len(words)} words')
