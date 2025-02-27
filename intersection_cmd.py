from file_manager import FileManager
from set_op_cmd import SetOpCommand
from arg import Arg

class Intersection(SetOpCommand):

  @staticmethod
  def cmd_name():
    return 'intersection'

  def aliases(self):
    return ['intersection', 'i']

  def set_operation(self, s1, s2):
    return s1 & s2
