import unittest
import io
import logging

from contextlib import redirect_stdout
from unittest.mock import MagicMock

from help_cmd import Help
from command_list import CommandList
from test_command import TestCommand
from file_manager import FileManager
from command_manager import CommandManager

logger = logging.getLogger(__name__)

class HelpTest(unittest.TestCase):

  def test_execute(self):
    cl = MagicMock(spec=CommandList)
    cmd1 = TestCommand()
    cmd2 = TestCommand()
    cmd1.cmd_name = lambda: 'abba'
    cmd1.name = 'abba'
    cmd2.overview = lambda: 'uwu'
    cl.cmds = {cmd1.name: cmd1, cmd2.name: cmd2}
    h = Help(cl)
    f = io.StringIO()
    with redirect_stdout(f):
      h.execute([], {})

    self.assertEqual(f.getvalue(), "abba: ['Arg[str]', 'Arg[int, opt]']\nuwu\n")

  def test_execute_correct_num_helps(self):
    fm = FileManager()
    cl = CommandList(fm)
    cm = CommandManager(cl)
    cm.initialize_commands()
    h = Help(cl)
    f = io.StringIO()
    with redirect_stdout(f):
      h.execute([], {})
    self.assertTrue('help' in f.getvalue())
    self.assertEqual(len(f.getvalue().strip().split('\n')), len(cl.cmd_list()))
