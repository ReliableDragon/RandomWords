import re
import logging

logger = logging.getLogger(__name__)

# Shared wording for any command that withholds an overwrite pending a yes.
# It lives here, on the base class every command descends from, so that
# alias_load and the set operations ask the same question rather than each
# inventing its own phrasing.
OVERWRITE_QUESTION = 'Alias exists. Overwrite? y/N'

# The same idea for a file on disk, which is not an alias and so gets its
# own wording rather than reusing OVERWRITE_QUESTION's.
OVERWRITE_FILE_QUESTION = 'File exists. Overwrite? y/N'

class Command():


  def __init__(self):
    self.name = self.cmd_name()


  @classmethod
  def create(cls, name):
    new_cmd = cls()
    new_cmd.name = name
    return new_cmd


  def check_match(self, regex, line):
    line = line.lower()
    match = re.fullmatch(regex, line)
    if not match:
      return False
    else:
      return True

  # Determine whether this command is being invoked. The default accepts
  # only the bare command word, with no arguments and no aliases. A command
  # whose syntax is richer than that -- an argument, a short alias, a
  # "bare" form -- overrides this itself, so that a reader finds the
  # accepted syntax in the command's own file rather than assembled from a
  # separate argument description.
  def matches(self, line):
    return self.check_match(self.name, line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  # A one-line usage summary for 'help'. The default is just the bare
  # command word; a command that takes arguments overrides this for a more
  # useful line.
  def overview(self):
    return self.name

  def execute(self, args_, context):
    pass

  @staticmethod
  def cmd_name():
    pass


  def __str__(self):
    return f"Command({self.name})"
