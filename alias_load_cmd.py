from file_manager import FileManager
from file_command import FileCommand
from arg import Arg

class AliasLoad(FileCommand):

  @staticmethod
  def cmd_name():
    return 'alias_load'

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(str, optional=True)]

  def overview(self):
    return 'alias_load [alias|al] alias filename(opt)'

  def matches(self, line):
    regex = r'(alias_load|alias|al) [\w_]+( [\w_.\/]+)?'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  def execute(self, args_, context):
    alias  = args_[0]
    filename = None
    words = None
    if len(args_) == 2:
      filename = args_[1]
      filename = self.fm.get_rooted(filename)
      try:
        words = self.fm.get_words(filename)
      except FileNotFoundError:
        print('File not found!')
        return None
    else:
      words = context['words']
    return {alias: words}

