import logging

from file_command import FileCommand
from command import OVERWRITE_QUESTION
from arg import Arg
from command_result import CommandResult
from file_manager import UnreadableSource

logger = logging.getLogger(__name__)

class SetOpCommand(FileCommand):

  def aliases(self):
    pass

  def set_operation(self, s1, s2):
    pass

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(str, optional=True), Arg(str, optional=True)]

  def overview(self):
    name = self.aliases()[0]
    aliases = ', '.join(self.aliases()[1:])
    return f'{name} [{aliases}] <alias|file.txt> [alias|file.txt] [out alias]'

  def matches(self, line):
    aliases = '|'.join(self.aliases())
    regex = rf'({aliases})( [\w_.\/]+){{1,3}}'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  # Resolves a name that is either a saved pool or a file on disk.
  def _get_words(self, name, context):
    if name in context:
      return context[name]
    return self.fm.get_words(name)

  def execute(self, args_, context):
    n1 = args_[0]
    if len(args_) == 1:
      # One argument: operate on the active pool and write back to it.
      n2 = n1
      n1 = 'words'
    else:
      n2 = args_[1]
    n3 = args_[2] if len(args_) == 3 else None

    if n3 is None and n1 not in context:
      msg = (f'"{n1}" is not a saved pool. With two arguments, '
             f'{self.aliases()[0]} writes its result back to the first one, '
             f'so that argument must be an alias. '
             f'Known names: {list(context.keys())}.')
      return CommandResult.fail(msg)

    try:
      w1 = self._get_words(n1, context)
      if not w1:
        return CommandResult.fail(f'"{n1}" has no words; nothing changed.')
      w2 = self._get_words(n2, context)
      if not w2:
        return CommandResult.fail(f'"{n2}" has no words; nothing changed.')
    except UnreadableSource as e:
      return CommandResult.fail(str(e))

    words = sorted(self.set_operation(set(w1), set(w2)))
    name = n3 if n3 is not None else n1
    updates = {name: words}
    data = {'pool': name, 'size': len(words)}

    # The one- and two-argument forms always write back to the active pool
    # or to the first operand, and that overwrite is the documented meaning
    # of those forms, not a mistake to guard against. Naming the first
    # operand as the explicit third argument is just those forms spelled
    # out, so it does not ask either. Only a third argument that names some
    # other pool that already exists needs a yes first, the same way
    # alias_load asks before it overwrites.
    if n3 is not None and n3 != n1 and n3 in context:
      return CommandResult(updates=updates, data=data, confirm=OVERWRITE_QUESTION)

    return CommandResult(updates=updates, data=data)
