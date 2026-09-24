import logging

from file_command import FileCommand
from file_manager import UnreadableSource
from command_result import CommandResult

logger = logging.getLogger(__name__)

class LoadRandDirFile(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load_rand_dir_file'

  def overview(self):
    return 'load_rand_dir_file [dr, drand, dir_random]'

  def matches(self, line):
    return line.strip().lower() in ['dr', 'drand', 'dir_random']

  def execute(self, args_, context):
    fname = self.fm.rand_dir()
    if fname is None:
      return CommandResult.fail('No .txt files found under /.')

    try:
      if hasattr(self.fm, 'get_words_and_counts'):
        words, counts = self.fm.get_words_and_counts(fname)
      else:
        words = self.fm.get_words(fname)
        counts = {w: 1 for w in words}
    except UnreadableSource as e:
      return CommandResult.fail(str(e))
    if not words:
      return CommandResult()

    return CommandResult(message=f'Loaded {fname}.',
                         updates={'words': words},
                         counts={'words': counts},
                         data={'source': fname, 'size': len(words)})
