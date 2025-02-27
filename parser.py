import logging
import os
import atexit
import readline

logger = logging.getLogger(__name__)

# Due to a Mac-specific error, this functionality
# does not work correctly across platforms.

# histfile = os.path.join(os.path.expanduser("~"), ".book_word_history")
# try:
#     readline.read_history_file(histfile)
#     # default history len is -1 (infinite), which may grow unruly
#     readline.set_history_length(1000)
# except FileNotFoundError:
#     pass

# atexit.register(readline.write_history_file, histfile)

class Parser():
  

  def __init__(self, command_list):
    self.cl = command_list

  
  def get_command(self) -> tuple['Command', list[str]]:
    cmd_found = False
    while not cmd_found:
      cmd_found = True
      raw_line = input('> ')
      cmd, args_ = self.parse(raw_line)
      if cmd == None:
        print("I'm sorry, I don't understand.")
        cmd_found = False
    return cmd, args_


  def parse(self, raw_line) -> tuple['Command', list[str]]:
    match = None
    length = -1
    base_cmd = None
    args_ = []
    for cmd_name, cmd in self.cl.cmds.items():
      if cmd.matches(raw_line):
        base_cmd = cmd
        args_ = cmd.parse_args(raw_line)
        break
    if not base_cmd:
      return None, []
    return base_cmd, args_

