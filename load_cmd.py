from arg import Arg
from file_command import FileCommand

class Load(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load'

  @staticmethod
  def cmd_args():
    return [Arg(str)]

  def overview(self):
    return 'load <file.txt or alias>  (a bare path ending in .txt works too)'

  def matches(self, line):
    regex = r'(load [\w\/]+(\.txt)?)|([\w\/]+\.txt)'
    return self.check_match(regex, line)

  def parse_args(self, line):
    line = line.strip()
    # The command word is matched case-insensitively, so strip it the same
    # way; the argument keeps the case it was typed in.
    if line.lower().startswith('load '):
      return [line[len('load '):].strip()]
    return [line]

  def execute(self, args_, context):
    source = args_[0]
    if source.endswith('.txt'):
      words = self.fm.get_words(source)
    elif source in context:
      words = context[source]
    else:
      print(f'Tried to load from context value {source}, but valid values are {list(context.keys())}.')
      return None

    if not words:
      print(f'No words found in {source}; keeping the current pool.')
      return None
    return {'words': words}
