import logging

from command import Command

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

  # Runs a command and merges whatever it returns into the context. A
  # 'result' key is handed back to the caller instead of being stored.
  def execute(self, cmd, args_):
    out_ctx = cmd.execute(args_, self.context)
    if out_ctx is None:
      return None

    result = None
    if 'result' in out_ctx:
      result = out_ctx.pop('result')
    self.context |= out_ctx
    return result
