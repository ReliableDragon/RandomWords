from arg import Arg
from file_command import FileCommand

class Load(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load'

  @staticmethod
  def cmd_args():
    return [Arg(str)]

  def matches(self, line):
    regex = r'(load [\w\/]+(\.txt)?)|([\w\/]+\.txt)'
    return self.check_match(regex, line)

  def parse_args(self, line):
    line = line.removeprefix('load ')
    return [line]

  def execute(self, args_, context):
    source = args_[0]
    words = None
    if source.endswith('.txt'):
      try:
        words = self.fm.get_words(source)
      except FileNotFoundError:
        print('File not found!')
        return None
    else:
      if not source in context:
        print(f'Tried to load from context value {source}, but valid values are {list(context.keys())}.')
      words = context[source]
    return {'words': words}
