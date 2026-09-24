from set_op_cmd import SetOpCommand

class Diff(SetOpCommand):

  @staticmethod
  def cmd_name():
    return 'diff'

  def aliases(self):
    return ['diff', 'd']

  def set_operation(self, s1, s2):
    return s1 - s2

  def combine_counts(self, words, c1, c2):
    return {w: c1.get(w, 1) for w in words}
