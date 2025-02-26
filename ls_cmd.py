import os
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

  # Print all relevant files under the directory passed
  # in, interpreting it either as a rooted path if it
  # starts with a '/' or as relative to the current
  # directory if it does not. If no directory is passed
  # in, then use the current directory. Prints the results
  # in user-friendly format, meaning only the "name" and
  # not the full path.
  def execute(self, args_, _):
    super().validate_args(args_)
    filename = None
    if args_:
      filename = args_[0]
      if not filename.startswith(self.fm.dir):
        filename = self.fm.get_path(filename)
    results = self.fm.ls(filename) 
    if results == None:
      print(f"File '{filename}' not found.")
      return []
    for path in results:
      basename = os.path.basename(path)

      if os.path.isdir(path):
        basename += '/'
        
      print(basename)
    
