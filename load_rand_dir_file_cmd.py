import logging

from file_command import FileCommand
from command_result import CommandResult
from file_manager import UnreadableSource

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
    return line.strip().lower() in ['dr', 'drand', 'dir_random']

  def execute(self, args_, context):
    fname = self.fm.rand_dir()
    if fname is None:
      return CommandResult.fail(f'No .txt files found under {self.fm.dir}.')
    try:
      words = self.fm.get_words(fname)
    except UnreadableSource as e:
      return CommandResult.fail(str(e))
    if not words:
      return CommandResult()
    return CommandResult(
      message=f'Loaded {fname}.',
      updates={'words': words},
      data={'source': fname, 'size': len(words)})
