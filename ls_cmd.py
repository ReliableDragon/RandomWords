import os

from file_command import FileCommand
from command_result import CommandResult

class LS(FileCommand):

  @staticmethod
  def cmd_name():
    return 'ls'

  def overview(self):
    return 'ls [folder]'

  def matches(self, line):
    regex = r'ls( [\w\/\.]+)?'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.split(' ')[1:]

  # Lists a folder of the library, or the root when none is given. Shows the
  # bare name of each entry, with a trailing slash on folders.
  def execute(self, args_, _):
    path = args_[0] if args_ else ''

    results = self.fm.ls(path)
    if results is None:
      return CommandResult.fail(f"Folder '{path or '/'}' not found.")

    lines = []
    entries = []
    for rel in results:
      name = os.path.basename(rel)
      is_dir = self.fm.is_dir(rel)
      lines.append(name + '/' if is_dir else name)
      entries.append({'name': name, 'path': rel, 'is_dir': is_dir})

    return CommandResult(message='\n'.join(lines), data={'entries': entries})
