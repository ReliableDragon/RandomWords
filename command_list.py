import logging

from ls_cmd import LS
from cd_cmd import CD
from pwd_cmd import PWD
from load_cmd import Load
from dump_cmd import Dump
from get_word_cmd import GetWord
from load_rand_file_cmd import LoadRandFile

logger = logging.getLogger(__name__)

class CommandList():

  def __init__(self, file_manager):
    self.cmds = {}
    self.fm = file_manager

  def has_cmd(self, name):
    name = name.lower()
    if not name in self.cmds:
      return False
    return True

  def get_cmd(self, name):
    name = name.lower()
    if not self.has_cmd(name):
      raise ValueError(f"Got invalid command '{name}'. Known commands are {self.cmds.keys()}")
    return self.cmds[name]

  def init_cmd(self, cmd):
    self.cmds[cmd.name] = cmd

  def cmd_list(self):
    cmds = [
      LS(self.fm),
      CD(self.fm),
      PWD(self.fm),
      Load(self.fm),
      Dump(),
      GetWord(),
      LoadRandFile(self.fm),
    ]
    return cmds
