from command import Command

class TestCommand(Command):

  def __init__(self):
    super().__init__()

  @staticmethod
  def cmd_name():
    return 'TestCommand'

  @staticmethod
  def cmd_args():
    return [str, int]

  def execute(self, args_, context):
    super().validate_args(args_)

    str_arg = args_[0]
    int_arg = args_[1]
    return {
      'result': str_arg * int_arg,
      'test_key': 24601
    } 
