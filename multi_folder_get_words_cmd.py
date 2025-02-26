import random
import logging

from file_command import FileCommand
from arg import Arg

logger = logging.getLogger(__name__)

class MultiFolderGetWords(FileCommand):

  @staticmethod
  def cmd_name():
    return 'multi_folder_get_words'

  @staticmethod
  def cmd_args():
    return [Arg(str, repeated=True)]

  def matches(self, line):
    regex = r'(multi_folder_get_words|mfgw|mul)( [\w_\/\.]+)+'
    return self.check_match(regex, line)

  def execute(self, args_, context):
    output = ''
    for fname in args_:
      if fname.endswith('.txt'):
        file = self.fm.get_rooted(fname)
        words = self.fm.get_words(file)
      elif fname in context:
        words = context[fname]
      else:
        folder = self.fm.get_rooted(fname)
        txts = self.fm.get_txts(folder)
        txt = random.choice(txts)
        words = self.fm.get_words(txt)
      word = random.choice(words)
      output += word + ' '
    # Remove trailing space
    output = output[:-1]
    print(output)
