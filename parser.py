

class Parser():
  

  def __init__(self, command_list):
    self.cl = command_list

  
  def get_command(self) -> tuple['Command', list[str]]:
    cmd_found = False
    while not cmd_found:
      cmd_found = True
      full_cmd = input('Input a command, or type "help" for help.\n')
      cmd, args_ = self.parse(full_cmd)
      if cmd == None:
        print("I'm sorry, I don't understand.")
        cmd_found = False
    return cmd, args_


  def parse(self, full_cmd) -> tuple['Command', list[str]]:
    cmd_frags = full_cmd.split(' ')
    base_cmd = cmd_frags[0]
    args_ = cmd_frags[1:]

    if not self.cl.has_cmd(base_cmd):
      return None, []
    cmd = self.cl.get_cmd(base_cmd)
    return cmd, args_

