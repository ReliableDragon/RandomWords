import logging

from file_command import FileCommand
from file_manager import UnreadableSource
from command_result import CommandResult

logger = logging.getLogger(__name__)

class LoadRandFile(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load_rand_file'

  def overview(self):
    return 'load_rand_file [r, rand, random] [folder]'

  def matches(self, line):
    regex = r'(r|rand|random)( [\w\/]+)?'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    folder = args_[0] if args_ else ''
    fname = self.fm.rand_file(folder)
    if fname is None:
      return CommandResult.fail(f'No .txt files found under {folder or "/"}.')

    try:
      words = self.fm.get_words(fname)
    except UnreadableSource as e:
      return CommandResult.fail(str(e))
    if not words:
      return CommandResult()

    return CommandResult(message=f'Loaded {fname}.',
                         updates={'words': words},
                         data={'source': fname, 'size': len(words)})
