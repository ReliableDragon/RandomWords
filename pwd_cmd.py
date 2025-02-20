from file_command import FileCommand

class PWD(FileCommand):

  @staticmethod
  def cmd_name():
    return 'pwd'

  @staticmethod
  def cmd_args():
    return []

  def execute(self, args_, _):
    super().validate_args(args_)
    pwd = self.fm.pwd()
    print(pwd)

