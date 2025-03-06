import logging

from file_manager import FileManager
from file_command import FileCommand
from arg import Arg

logger = logging.getLogger(__name__)

class SetOpCommand(FileCommand):

  def aliases(self):
    pass

  def set_operation(self, s1, s2):
    pass

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(str), Arg(str, optional=True)]

  def overview(self):
    name = self.aliases()[0]
    aliases = '|'.join(self.aliases()[1:])
    return f'{name} [{aliases}] in(/out){{alias, filename*}}(opt) in{{alias, filename}} out{{alias}}(opt)'

  def matches(self, line):
    aliases = '|'.join(self.aliases())
    regex = rf'({aliases})( [\w_.\/]+){{1,3}}'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  def execute(self, args_, context):
    out_ctx = {}
    n1 = args_[0]
    if len(args_) == 1:
      n2 = n1
      n1 = 'words'
    else:
      n2 = args_[1]
    n3 = None
    if len(args_) == 3:
      n3 = args_[2]

    w1 = None
    if n3 == None:
      assert n1 in context, f'Got name {n1} as first argument to two-parameter version of diff, but context only contained {context}'
    if n1 in context:
      w1 = context[n1]
    else:
      n1 = self.fm.get_rooted(n1)
      w1 = self.fm.get_words(n1)
      if not w1:
        return None

    w2 = None
    if n2 in context:
      w2 = context[n2]
    else:
      n2 = self.fm.get_rooted(n2)
      w2 = self.fm.get_words(n2)
    if not w2: return None

    words = list(self.set_operation(set(w1), set(w2)))
    if n3 != None:
      out_ctx[n3] = words
    else:
      out_ctx[n1] = words
    return out_ctx

