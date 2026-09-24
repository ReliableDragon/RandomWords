import logging

from functools import reduce

from file_command import FileCommand
from command import OVERWRITE_QUESTION
from command_result import CommandResult
from file_manager import UnreadableSource

logger = logging.getLogger(__name__)

class SetOpCommand(FileCommand):

  def aliases(self):
    pass

  def set_operation(self, s1, s2):
    pass

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
    words, _ = self._get_words_and_counts(name, context)
    return words

  def _get_words_and_counts(self, name, context):
    if name in context:
      words = context[name]
      counts = getattr(context, 'counts', {}).get(name, {w: 1 for w in words})
      return words, counts
    if hasattr(self.fm, 'get_words_and_counts'):
      return self.fm.get_words_and_counts(name)
    words = self.fm.get_words(name)
    return words, {w: 1 for w in words}

  def combine_counts(self, words, c1, c2):
    return {w: c1.get(w, 0) + c2.get(w, 0) for w in words}

  def execute(self, args_, context):
    if len(args_) == 1:
      # One argument: operate on the active pool and write back to it.
      sources = ['words', args_[0]]
      out = None
    elif len(args_) == 2:
      sources = args_
      out = None
    else:
      # Three or more: everything but the last is a source, the last is
      # always the explicit output name. This is exactly the three-argument
      # form (n1, n2, out) generalized -- it is what already made a third
      # argument unambiguous, and it keeps working the same way how ever
      # many sources come before it.
      sources = args_[:-1]
      out = args_[-1]

    n1 = sources[0]
    if out is None and n1 not in context:
      msg = (f'"{n1}" is not a saved pool. With two arguments, '
             f'{self.aliases()[0]} writes its result back to the first one, '
             f'so that argument must be an alias. '
             f'Known names: {list(context.keys())}.')
      return CommandResult.fail(msg)

    try:
      resolved = []
      for name in sources:
        words, counts = self._get_words_and_counts(name, context)
        if not words:
          return CommandResult.fail(f'"{name}" has no words; nothing changed.')
        resolved.append((words, counts))
    except UnreadableSource as e:
      return CommandResult.fail(str(e))

    word_sets = [set(words) for words, _ in resolved]
    words = sorted(reduce(self.set_operation, word_sets))
    counts = reduce(lambda acc, pair: self.combine_counts(words, acc, pair[1]),
                     resolved[1:], resolved[0][1])
    name = out if out is not None else n1
    updates = {name: words}
    counts_map = {name: counts}
    tokens = sum(counts.values()) if counts else len(words)
    data = {'pool': name, 'size': len(words), 'tokens': tokens}

    # The one- and two-argument forms always write back to the active pool
    # or to the first operand, and that overwrite is the documented meaning
    # of those forms, not a mistake to guard against. Naming the first
    # operand as the explicit output name is just those forms spelled out,
    # so it does not ask either. Only an output name that names some other
    # pool that already exists needs a yes first, the same way alias_load
    # asks before it overwrites.
    if out is not None and out != n1 and out in context:
      return CommandResult(updates=updates, counts=counts_map, data=data, confirm=OVERWRITE_QUESTION)

    return CommandResult(updates=updates, counts=counts_map, data=data)
