import logging

from command import Command
from command_result import CommandResult

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

UNKNOWN_COMMAND = "I'm sorry, I don't understand."


# What to show when no command claims a line. It is a CommandResult like any
# other so that a browser can render it the same way it renders everything
# else, rather than the parser writing to a terminal nobody may be watching.
def unknown_command_result() -> CommandResult:
  return CommandResult.fail(UNKNOWN_COMMAND)


class Parser():


  def __init__(self, command_list):
    self.cl = command_list


  # Reads one line and resolves it. A line nothing claims comes back as
  # (None, []); the caller decides what to say about it.
  def get_command(self) -> tuple[Command, list[str]]:
    return self.parse(input('> '))


  # Finds the first registered command that claims this line. Registration
  # order in CommandList.cmd_list therefore decides precedence.
  def parse(self, raw_line) -> tuple[Command, list[str]]:
    raw_line = raw_line.strip()
    for _, cmd in self.cl.cmds.items():
      if cmd.matches(raw_line):
        return cmd, cmd.parse_args(raw_line)
    return None, []
