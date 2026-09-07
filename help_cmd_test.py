import unittest
import logging

from unittest.mock import MagicMock

from help_cmd import Help
from command_list import CommandList
from fake_command import FakeCommand
from file_manager import FileManager
from command_manager import CommandManager

logger = logging.getLogger(__name__)

class HelpTest(unittest.TestCase):

  def test_execute(self):
    cl = MagicMock(spec=CommandList)
    cmd1 = FakeCommand()
    cmd2 = FakeCommand()
    cmd1.cmd_name = lambda: 'abba'
    cmd1.name = 'abba'
    cmd2.overview = lambda: 'uwu'
    cl.cmds = {cmd1.name: cmd1, cmd2.name: cmd2}
    h = Help(cl)
    result = h.execute([], {})

    self.assertEqual(result.message, 'abba <str> [int]\nuwu')

  def test_execute_correct_num_helps(self):
    fm = FileManager()
    cl = CommandList(fm)
    cm = CommandManager(cl)
    cm.initialize_commands()
    h = Help(cl)
    result = h.execute([], {})
    self.assertTrue('help' in result.message)
    self.assertEqual(len(result.message.strip().split('\n')), len(cl.cmd_list()))
