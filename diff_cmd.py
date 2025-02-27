from file_manager import FileManager
from set_op_cmd import SetOpCommand
from arg import Arg

class Diff(SetOpCommand):

  @staticmethod
  def cmd_name():
    return 'diff'

  def aliases(self):
    return ['diff', 'd']

  def set_operation(self, s1, s2):
    return s1 - s2
