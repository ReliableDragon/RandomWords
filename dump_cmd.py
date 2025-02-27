from command import Command
from arg import Arg

class Dump(Command):

  @staticmethod
  def cmd_name():
    return 'dump'

  @staticmethod
  def cmd_args():
    return [Arg(bool, optional=True)]

  def execute(self, args_, context):
    dump_all = False
    if args_:
      dump_all = bool(args_[0])
    if dump_all:
      print(f"context: {context}")
    else:
      print(f"context: {list(context.keys())}")
