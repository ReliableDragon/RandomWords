import random
import logging

from file_command import FileCommand
from arg import Arg
from command_result import CommandResult

logger = logging.getLogger(__name__)

class MultiFolderGetWords(FileCommand):

  @staticmethod
  def cmd_name():
    return 'multi_folder_get_words'

  @staticmethod
  def cmd_args():
    return [Arg(str, repeated=True)]

  def overview(self):
    return 'multi_folder_get_words [mfgw, mul] {folder, file.txt or alias}+'

  def matches(self, line):
    regex = r'(multi_folder_get_words|mfgw|mul)( [\w_\/\.]+)+'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    output = []
    for name in args_:
      if name.endswith('.txt'):
        words = self.fm.get_words(name)
      elif name in context:
        words = context[name]
      else:
        folder = self.fm.get_rooted(name)
        txts = self.fm.get_txts(folder)
        if not txts:
          return CommandResult.fail(f'No .txt files found under {name}.')
        words = self.fm.get_words(random.choice(txts))
      if not words:
        return CommandResult.fail(f'No words found for {name}.')
      output.append(random.choice(words))
    return CommandResult(message=' '.join(output), data={'drawn': output})
