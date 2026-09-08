import logging

from dataclasses import replace

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
  #
  # This is the one place both front ends' yes arrives: the terminal calls
  # it directly, and the browser's "answer with force" reaches it through
  # apply_if_forced. A command whose confirmation needs more than a context
  # merge -- writing a file, which is a real side effect and not something
  # `updates` can hold pending -- leaves an `on_confirm` callback on the
  # result for exactly this moment, when the answer is finally known to be
  # yes.
  def apply(self, result: CommandResult) -> CommandResult:
    if not result.ok:
      return result
    self._merge(result)
    if result.on_confirm is None:
      return result
    try:
      message = result.on_confirm()
    except (InvalidPath, UnreadableSource) as e:
      return CommandResult.fail(str(e))
    return replace(result, message=message, confirm='')

  def _merge(self, result: CommandResult):
    for name in result.removes:
      self.context.pop(name, None)
    if result.updates:
      self.context |= result.updates
