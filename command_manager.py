import logging

from dataclasses import replace

from command import Command
from command_result import CommandResult
from file_manager import InvalidPath, UnreadableSource

logger = logging.getLogger(__name__)

class Context(dict):
  """The dictionary of word pools held by a CommandManager.

  Inherits from dict so that every existing command, test, and serializer
  that treats context as a dict[str, list[str]] continues to work without
  modification. Additional session metadata (pool occurrence counts and
  sampling mode) is kept on attributes rather than as dictionary keys,
  preserving the invariant that context keys are pool names and nothing else.
  """

  def __init__(self, *args, counts=None, sampling_mode='uniform', **kwargs):
    super().__init__(*args, **kwargs)
    self.counts = {} if counts is None else counts
    self.sampling_mode = sampling_mode


class CommandManager():

  def __init__(self, command_list, context=None):
    self.command_list = command_list
    # A fresh dict per manager; a shared default would leak state between
    # instances.
    if isinstance(context, Context):
      self.context = context
    elif context is not None:
      self.context = Context(context)
    else:
      self.context = Context()

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

  def get_counts(self, pool_name: str) -> dict[str, int]:
    if hasattr(self.context, 'counts') and pool_name in self.context.counts:
      return self.context.counts[pool_name]
    if pool_name in self.context and isinstance(self.context[pool_name], list):
      return {w: 1 for w in self.context[pool_name]}
    return {}

  def get_sampling_mode(self) -> str:
    return getattr(self.context, 'sampling_mode', 'uniform')

  def set_sampling_mode(self, mode: str) -> None:
    if hasattr(self.context, 'sampling_mode'):
      self.context.sampling_mode = mode

  def _merge(self, result: CommandResult):
    for name in result.removes:
      self.context.pop(name, None)
      if hasattr(self.context, 'counts'):
        self.context.counts.pop(name, None)
    if result.updates:
      self.context |= result.updates
    if result.counts and hasattr(self.context, 'counts'):
      self.context.counts |= result.counts
