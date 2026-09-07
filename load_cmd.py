from arg import Arg
from command_result import CommandResult
from file_command import FileCommand
from file_manager import UnreadableSource

class Load(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load'

  @staticmethod
  def cmd_args():
    return [Arg(str)]

  def overview(self):
    return 'load <file.txt or alias>  (a bare path ending in .txt works too)'

  def matches(self, line):
    regex = r'(load [\w\/]+(\.txt)?)|([\w\/]+\.txt)'
    return self.check_match(regex, line)

  def parse_args(self, line):
    line = line.strip()
    # The command word is matched case-insensitively, so strip it the same
    # way; the argument keeps the case it was typed in.
    if line.lower().startswith('load '):
      return [line[len('load '):].strip()]
    return [line]

  def execute(self, args_, context):
    source = args_[0]
    # Anything with a slash is meant as a path, even without the extension.
    # Treating it as an alias name instead produced a baffling error for
    # something like `load /etc/passwd`.
    if source.endswith('.txt') or '/' in source:
      try:
        words = self.fm.get_words(source)
      except UnreadableSource as e:
        return CommandResult.fail(
            f'{e}\nNo words found in {source}; keeping the current pool.')
    elif source in context:
      words = context[source]
    else:
      return CommandResult.fail(f'Tried to load from context value {source}, but valid values are {list(context.keys())}.')

    if not words:
      return CommandResult.fail(f'No words found in {source}; keeping the current pool.')
    return CommandResult(updates={'words': words}, data={'size': len(words)})
