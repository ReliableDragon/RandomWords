import logging

from ls_cmd import LS
from command import Command
from typing import Any

from command_list import CommandList

logger = logging.getLogger(__name__)

class CommandManager():

  def __init__(self, command_list, context={}):
    self.command_list = command_list
    self.context = context

  def initialize_commands(self):
    self._initialize_commands(self.command_list.cmd_list())

  def _initialize_commands(self, cmds: list[Command]):
    for cmd in cmds:
      self.command_list.init_cmd(cmd)

  def execute(self, cmd, args_):
    out_ctx = cmd.execute(args_, self.context)
    if out_ctx == None:
      return None
      
    result = None
    if 'result' in out_ctx:
      result = out_ctx.pop('result')
    self.context |= out_ctx
    return result


