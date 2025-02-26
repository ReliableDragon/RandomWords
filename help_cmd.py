import logging

from command import Command

logger = logging.getLogger(__name__)

class Help(Command):

  def __init__(self, command_list):
    super().__init__()
    self.command_list = command_list

  @staticmethod
  def cmd_name():
    return 'help'

  @staticmethod
  def cmd_args():
    return []

  def execute(self, args_, context):
    output = ''
    for _, cmd in self.command_list.cmds.items():
      output += cmd.overview()
      output += '\n'
    # Strip trailing newline
    output = output[:-1]
    print(output)
