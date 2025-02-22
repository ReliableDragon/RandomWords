import logging

from file_command import FileCommand

logger = logging.getLogger(__name__)

class LoadRandFile(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load_rand_file'

  @staticmethod
  def cmd_args():
    return []

  def matches(self, line):
    if line in ['r', 'rand', 'random']:
      return True
    return False

  def execute(self, args_, context):
    fname = self.fm.rand_file()
    logger.warning(fname)
    words = self.fm.get_words(fname)
    return {'words': words}
