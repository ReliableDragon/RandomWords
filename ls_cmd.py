import file_manager

from arg import Arg
from file_command import FileCommand

class LS(FileCommand):

  @staticmethod
  def cmd_name():
    return 'ls'

  @staticmethod
  def cmd_args():
    return [Arg(str, optional=True)]

  def matches(self, line):
    regex = r'ls( \w+)?'
    return self.check_match(regex, line)

  def parse_args(self, line):
    args = line.split(' ')[1:]
    if not args:
      return []
    return args

  def execute(self, args_, _):
    super().validate_args(args_)
    dir_ = None
    if args_:
      dir_ = args_[0]
      if not dir_.startswith(file_manager.ROOT_DIR):
        dir_ = self.fm.get_path(dir_)
    try:
      results = self.fm.ls(dir_) 
    except FileNotFoundError:
      print(f"File '{dir_}' not found.")
      return []
    for r in results:
      if r.is_dir():
        print(r.name + '/')
      else:
        print(r.name)
    
