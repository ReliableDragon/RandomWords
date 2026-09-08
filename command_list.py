import logging

from ls_cmd import LS
from load_cmd import Load
from dump_cmd import Dump
from get_word_cmd import GetWord
from load_rand_file_cmd import LoadRandFile
from get_alias_words_cmd import GetAliasWords
from alias_load_cmd import AliasLoad
from save_cmd import Save
from help_cmd import Help
from multi_folder_get_words_cmd import MultiFolderGetWords
from load_rand_dir_file_cmd import LoadRandDirFile
from combine_cmd import Combine
from diff_cmd import Diff
from intersection_cmd import Intersection
from rand_diff_cmd import RandDiff
from forget_cmd import Forget
from quit_cmd import Quit
from which_cmd import Which
from rare_cmd import Rare
from like_cmd import Like
from word_index import WordIndex

logger = logging.getLogger(__name__)

class CommandList():

  def __init__(self, file_manager, index=None):
    self.cmds = {}
    self.fm = file_manager
    # Built here when nobody supplied one so that book_word.py keeps its
    # one-argument construction. It reads nothing until a command asks it
    # to, so an unused index costs a session nothing.
    self.index = index if index is not None else WordIndex(file_manager)

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

  # TODO: Consider passing self to commands
  # so that commands can call other commands.
  def cmd_list(self):
    cmds = [
      LS(self.fm),
      Load(self.fm),
      Dump(),
      GetWord(),
      LoadRandFile(self.fm),
      AliasLoad(self.fm),
      Save(self.fm),
      GetAliasWords(),
      Help(self),
      MultiFolderGetWords(self.fm),
      LoadRandDirFile(self.fm),
      Combine(self.fm),
      Diff(self.fm),
      Intersection(self.fm),
      RandDiff(self),
      Forget(),
      Quit(),
      Which(self.index),
      Rare(self.index),
      Like(self.index)
    ]
    return cmds
