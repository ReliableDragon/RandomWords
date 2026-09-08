import logging

from command import Command
from command_result import CommandResult

logger = logging.getLogger(__name__)

class Help(Command):

  def __init__(self, command_list):
    super().__init__()
    self.command_list = command_list

  @staticmethod
  def cmd_name():
    return 'help'

  # No arguments and no aliases: 'help' is the only spelling. This is also
  # what the base class's default matches() would give a zero-argument
  # command, but it is spelled out here so the syntax is visible without
  # having to go read the base class.
  def matches(self, line):
    return self.check_match('help', line)

  def execute(self, args_, context):
    output = ''
    lines = []
    for _, cmd in self.command_list.cmds.items():
      overview = cmd.overview()
      lines.append(overview)
      output += overview
      output += '\n'
    # Strip trailing newline
    output = output[:-1]
    return CommandResult(message=output, data={'commands': lines})
