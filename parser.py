import logging

from command import Command

logger = logging.getLogger(__name__)

# Gives the input() prompt line editing and history. readline is optional and
# is missing on some platforms (notably Windows), so its absence must not
# stop the program from starting.
try:
  import readline  # noqa: F401
except ImportError:
  logger.debug('readline is unavailable; line editing is disabled.')

# Note: reading and writing a history file was tried here and behaved badly
# with the libedit-backed readline shipped on macOS, so history is per-session
# only.


class Parser():


  def __init__(self, command_list):
    self.cl = command_list


  def get_command(self) -> tuple['Command', list[str]]:
    cmd = None
    while cmd is None:
      raw_line = input('> ')
      cmd, args_ = self.parse(raw_line)
      if cmd is None:
        print("I'm sorry, I don't understand.")
    return cmd, args_


  # Finds the first registered command that claims this line. Registration
  # order in CommandList.cmd_list therefore decides precedence.
  def parse(self, raw_line) -> tuple['Command', list[str]]:
    raw_line = raw_line.strip()
    for _, cmd in self.cl.cmds.items():
      if cmd.matches(raw_line):
        return cmd, cmd.parse_args(raw_line)
    return None, []
