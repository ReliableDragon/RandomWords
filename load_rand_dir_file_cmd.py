import logging

from file_command import FileCommand

logger = logging.getLogger(__name__)

class LoadRandDirFile(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load_rand_dir_file'

  @staticmethod
  def cmd_args():
    return []

  def overview(self):
    return 'load_rand_dir_file [dr, drand, dir_random]'

  def matches(self, line):
    if line in ['dr', 'drand', 'dir_random']:
      return True
    return False

  def execute(self, args_, context):
    fname = self.fm.rand_dir()
    print(f'Loaded {fname}.')
    words = self.fm.get_words(fname)
    return {'words': words}
