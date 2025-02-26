from file_manager import FileManager
from file_command import FileCommand
from arg import Arg

class AliasLoad(FileCommand):

  @staticmethod
  def cmd_name():
    return 'alias_load'

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(str)]

  def matches(self, line):
    regex = r'(alias_load|al) [\w_]+ [\w_.\/]+'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  def execute(self, args_, context):
    alias  = args_[0]
    filename = args_[1]
    words = None
    try:
      words = self.fm.get_words(filename)
    except FileNotFoundError:
      print('File not found!')
      return None
    return {alias: words}

