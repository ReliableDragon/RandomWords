from set_op_cmd import SetOpCommand

class Combine(SetOpCommand):

  @staticmethod
  def cmd_name():
    return 'combine'

  def aliases(self):
    return ['combine', 'c']

  def set_operation(self, s1, s2):
    return s1 | s2

