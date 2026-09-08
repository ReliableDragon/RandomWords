import re
import logging
import itertools

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
    self.args = self.cmd_args()


  @classmethod
  def create(cls, name, args_):
    new_cmd = cls()
    new_cmd.name = name
    new_cmd.args = args_
    return new_cmd


  def validate_args(self, values: list):
    for value, arg in itertools.zip_longest(values, self.args):
      if arg is None or not arg.validate(value):
        raise ValueError(f"Got incorrect arg type(s)!\nExpected: {[str(arg) for arg in self.args]}\nBut was: {[type(v) for v in values]}")

  def check_match(self, regex, line):
    line = line.lower()
    match = re.fullmatch(regex, line)
    if not match:
      return False
    else:
      return True

  # Determine whether this command is being invoked. If this method
  # is not overridden, defaults to the command's name plus space-separated arguments.
  def matches(self, line):
    regex = self.name
    for arg in self.args:
      if arg.optional:
        regex += r'( [^ ]+)?'
      else:
        regex += r' [^ ]+'
    return self.check_match(regex, line)

  def parse_args(self, line):
    if not self.args:
      return []
    return line.split(' ')[1:]

  # A one-line usage summary for 'help'. Commands with aliases or a
  # non-standard syntax override this.
  def overview(self):
    parts = [self.name]
    for arg in self.args or []:
      name = arg.type.__name__
      if arg.repeated:
        name += '...'
      parts.append(f'[{name}]' if arg.optional else f'<{name}>')
    return ' '.join(parts)

  def execute(self, args_, context):
    pass

  @staticmethod
  def cmd_name():
    pass

  @staticmethod
  def cmd_args():
    pass


  def __str__(self):
    return f"Command({self.name}){[str(arg) for arg in self.args]}"
