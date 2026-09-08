from command import OVERWRITE_FILE_QUESTION
from command_result import CommandResult
from file_command import FileCommand

ACTIVE_POOL = 'words'


class Save(FileCommand):
  """Writes a pool to disk, under sources/custom/, so it survives a restart."""

  @staticmethod
  def cmd_name():
    return 'save'

  def overview(self):
    return 'save <name> [pool]: write a pool to disk, as custom/<name>.txt'

  # "save" followed by one or two space-separated tokens. The name is not
  # given a tighter pattern here, because it is not validated as syntax at
  # all; FileManager.write_path is what decides whether it can be a
  # filename, with a message aimed at whoever typed it rather than a silent
  # "I don't understand" from the parser.
  def matches(self, line):
    return self.check_match(r'save [^ ]+( [^ ]+)?', line)

  def execute(self, args_, context):
    name = args_[0]

    if len(args_) == 2:
      pool = args_[1]
      if pool not in context:
        return CommandResult.fail(
            f'"{pool}" is not a saved pool. Known names: {list(context.keys())}.')
      words = context[pool]
    else:
      pool = ACTIVE_POOL
      words = context.get(ACTIVE_POOL)

    if not words:
      if len(args_) == 2:
        return CommandResult.fail(f'"{pool}" has no words; nothing written.')
      return CommandResult.fail('No words are loaded, so there is nothing to write.')

    # write_path both validates `name` and tells us where the words would
    # land; letting InvalidPath propagate from here is what
    # CommandManager.execute already does for every other command's bad
    # path, so there is nothing more for this method to catch.
    path = self.fm.relative(self.fm.write_path(name))
    data = {'name': name, 'pool': pool, 'size': len(words), 'path': path}

    if self.fm.pool_exists(name):
      # The write cannot happen through `updates`; CommandManager.apply
      # only merges context entries, and a file on disk is not one of
      # those. `on_confirm` is the callback apply runs once the answer is
      # known to be yes -- the one point both front ends' yes reaches,
      # whichever one asked the question above.
      return CommandResult(data=data, confirm=OVERWRITE_FILE_QUESTION,
                           on_confirm=lambda: self._write(name, words, path))

    return CommandResult(message=self._write(name, words, path), data=data)

  def _write(self, name, words, path):
    self.fm.write_pool(name, words)
    return f'Wrote {len(words):,} words to {path}.'
