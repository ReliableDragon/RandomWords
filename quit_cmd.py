from command import Command

class Quit(Command):

  @staticmethod
  def cmd_name():
    return 'quit'

  @staticmethod
  def cmd_args():
    return []

  def overview(self):
    return 'quit [exit, q]'

  def matches(self, line):
    return line.strip().lower() in ['quit', 'exit', 'q']

  def execute(self, args_, context):
    return {'result': 'quit'}
