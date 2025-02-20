from file_command import FileCommand

class LS(FileCommand):

  @staticmethod
  def cmd_name():
    return 'ls'

  @staticmethod
  def cmd_args():
    return []

  def execute(self, args_, _):
    super().validate_args(args_)
    results = self.fm.ls() 
    for r in results:
      print(str(r))
    
