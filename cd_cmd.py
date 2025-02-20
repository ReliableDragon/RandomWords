from file_command import FileCommand

class CD(FileCommand):

  @staticmethod
  def cmd_name():
    return 'cd'

  @staticmethod
  def cmd_args():
    return [str]

  def execute(self, args_, _):
    super().validate_args(args_)
    path = args_[0]
    self.fm.cd(path)


