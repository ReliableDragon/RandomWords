from command_result import CommandResult
from file_command import FileCommand
from file_manager import UnreadableSource

class Load(FileCommand):

  @staticmethod
  def cmd_name():
    return 'load'

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
        if hasattr(self.fm, 'get_words_and_counts'):
          words, counts = self.fm.get_words_and_counts(source)
        else:
          words = self.fm.get_words(source)
          counts = {w: 1 for w in words}
      except UnreadableSource as e:
        return CommandResult.fail(
            f'{e}\nNo words found in {source}; keeping the current pool.')
    elif source in context:
      words = context[source]
      counts = getattr(context, 'counts', {}).get(source, {w: 1 for w in words})
    else:
      return CommandResult.fail(f'Tried to load from context value {source}, but valid values are {list(context.keys())}.')

    if not words:
      return CommandResult.fail(f'No words found in {source}; keeping the current pool.')
    # The source travels with the result so a front end can name the pool.
    # Without it a load typed at the command line left the page still
    # naming whatever had been loaded by button before it.
    return CommandResult(updates={'words': words},
                         counts={'words': counts},
                         data={'size': len(words), 'source': source})
