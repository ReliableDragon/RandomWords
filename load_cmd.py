from file_command import FileCommand

class Load(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load'

  @staticmethod
  def cmd_args():
    return [str]

  def matches(self, line):
    regex = r'\w+\.txt'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return [line]

  # TODO: Standardize filenames to either be
  # relative to current directory or absolute
  # from the root; currently they're mixed.
  def execute(self, args_, context):
    filename = args_[0]
    words = None
    try:
      words = self.fm.get_words(filename)
    except FileNotFoundError:
      print('File not found!')
      return None
    return {'words': words}
