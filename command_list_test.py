import unittest
import logging

from command import Command
from command_list import CommandList
from file_manager import FileManager
from unittest.mock import MagicMock, patch

logger = logging.getLogger(__name__)

class CommandListTest(unittest.TestCase):

  def setUp(self):
    self.mock_fm = MagicMock(spec=FileManager)
    self.mock_cmd = MagicMock(spec=Command)
    self.mock_cmd.name = 'hurble' 
    self.mock_cmd_list = patch.object(CommandList, 'cmd_list', return_value = [self.mock_cmd])

  def init_cl(self):
    self.cl = CommandList(self.mock_fm)
    self.cl.init_cmd(self.mock_cmd)

  def test_init_cmd(self):
    with self.mock_cmd_list:
      cl = CommandList(self.mock_fm)
      for cmd in CommandList.cmd_list():
        cl.init_cmd(cmd)
      self.assertEqual(cl.cmds, {'hurble': self.mock_cmd})

  def test_has_cmd(self):
    with self.mock_cmd_list:
      self.init_cl()

      hurble_result = self.cl.has_cmd('hurble')
      burble_result = self.cl.has_cmd('burble')

      self.assertEqual(hurble_result, True)
      self.assertEqual(burble_result, False)

  
  def test_get_cmd(self):
    with self.mock_cmd_list:
      self.init_cl()

      hurble_result = self.cl.get_cmd('hurble')
      self.assertEqual(hurble_result, self.mock_cmd)

  def test_get_cmd_err(self):
    with self.mock_cmd_list:
      with self.assertRaises(ValueError):
        self.init_cl()

        burble_result = self.cl.get_cmd('burble')


