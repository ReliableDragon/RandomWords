import os

from arg import Arg
from command_result import CommandResult
from file_command import FileCommand

class CD(FileCommand):

  @staticmethod
  def cmd_name():
    return 'cd'

  @staticmethod
  def cmd_args():
    return [Arg(str)]

  def overview(self):
    return 'cd <folder>  (".." to go up, "/" for the sources root)'

  def execute(self, args_, _):
    super().validate_args(args_)
    path = args_[0]
    previous = self.fm.dir
    self.fm.cd(path)
    if not os.path.isdir(self.fm.dir):
      self.fm.dir = previous
      return CommandResult.fail(f'No such folder: {path}')
    return CommandResult()
