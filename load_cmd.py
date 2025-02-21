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

  def execute(self, args_, context):
    filename = args_[0]
    self.fm.filename = filename
    words = None
    try:
      words = self.fm.get_words()
    except FileNotFoundError:
      print('File not found!')
      self.fm.filename = None
      return None
    return {'words': words}
