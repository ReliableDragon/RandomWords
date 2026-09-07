import logging

from command import Command
from command_result import CommandResult
from file_manager import InvalidPath, UnreadableSource

logger = logging.getLogger(__name__)

class CommandManager():

  def __init__(self, command_list, context=None):
    self.command_list = command_list
    # A fresh dict per manager; a shared default would leak state between
    # instances.
    self.context = {} if context is None else context

  def initialize_commands(self):
    self._initialize_commands(self.command_list.cmd_list())

  def _initialize_commands(self, cmds: list[Command]):
    for cmd in cmds:
      self.command_list.init_cmd(cmd)

  # Runs a command and merges what it produced into the context.
  #
  # The merge happens here rather than in each command so that the rule holds
  # in one place: a command that failed, or that is still waiting for a
  # confirmation, changes nothing.
  def execute(self, cmd, args_) -> CommandResult:
    try:
      result = cmd.execute(args_, self.context)
    except (InvalidPath, UnreadableSource) as e:
      # A path the library refuses is a user error with one wording, not a
      # crash, and not something every command should have to guard.
      return CommandResult.fail(str(e))
    if result.ok and not result.confirm:
      self._merge(result)
    return result

  # Applies updates that were withheld pending a confirmation, once the
  # front end has its yes.
  def apply(self, result: CommandResult) -> CommandResult:
    if result.ok:
      self._merge(result)
    return result

  def _merge(self, result: CommandResult):
    for name in result.removes:
      self.context.pop(name, None)
    if result.updates:
      self.context |= result.updates
