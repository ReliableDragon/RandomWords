from command import Command

class Dump(Command):

  @staticmethod
  def cmd_name():
    return 'dump'

  @staticmethod
  def cmd_args():
    return []

  def execute(self, args_, context):
    print(f"context: {str(context)}")
