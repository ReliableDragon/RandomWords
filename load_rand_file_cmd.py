import logging

from file_command import FileCommand
from arg import Arg

logger = logging.getLogger(__name__)

class LoadRandFile(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load_rand_file'

  @staticmethod
  def cmd_args():
    return [Arg(str, optional=True)]

  def overview(self):
    return 'load_rand_file [r, rand, random]'

  def matches(self, line):
    regex = r'(r|rand|random)( [\w\/]+)?'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    folder = None
    if args_:
      folder = args_[0]
      folder = self.fm.get_rooted(folder)
    fname = self.fm.rand_file(folder)
    print(f'Loaded {fname}.')
    words = self.fm.get_words(fname)
    return {'words': words}
