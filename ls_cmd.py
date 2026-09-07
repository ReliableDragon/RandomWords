import os

from arg import Arg
from command_result import CommandResult
from file_command import FileCommand

class LS(FileCommand):

  @staticmethod
  def cmd_name():
    return 'ls'

  @staticmethod
  def cmd_args():
    return [Arg(str, optional=True)]

  def overview(self):
    return 'ls [folder]'

  def matches(self, line):
    regex = r'ls( \w+)?'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.split(' ')[1:]

  # Print all relevant files under the directory passed
  # in, interpreting it either as a rooted path if it
  # starts with a '/' or as relative to the current
  # directory if it does not. If no directory is passed
  # in, then use the current directory. Prints the results
  # in user-friendly format, meaning only the "name" and
  # not the full path.
  def execute(self, args_, _):
    super().validate_args(args_)
    filename = None
    if args_:
      filename = args_[0]
      if not filename.startswith(self.fm.dir):
        filename = self.fm.get_path(filename)
    results = self.fm.ls(filename)
    if results is None:
      return CommandResult.fail(f"File '{filename or self.fm.dir}' not found.")
    lines = []
    entries = []
    for path in sorted(results):
      basename = os.path.basename(path)
      is_dir = os.path.isdir(path)

      display = basename + '/' if is_dir else basename
      lines.append(display)
      entries.append({'name': basename, 'is_dir': is_dir})

    return CommandResult(message='\n'.join(lines), data={'entries': entries})
