import unittest
import logging

from command import Command
from command_list import CommandList
from file_manager import FileManager
from unittest.mock import MagicMock
from test_command import TestCommand

logger = logging.getLogger(__name__)

class TestCommandList(unittest.TestCase):

  def setUp(self):
    self.test_cmd = TestCommand()
    self.test_cmd.name = 'hurble'
    self.fm = FileManager()
    self.cl = CommandList(self.fm)
    self.orig_cmd_list = self.cl.cmd_list
    self.cl.cmd_list = MagicMock(return_value=[self.test_cmd])

  def tearDown(self):
    self.cl.cmd_list = self.orig_cmd_list

  def init_cl(self):
    self.cl.init_cmd(self.test_cmd)

  def test_init_cmd(self):
    for cmd in self.cl.cmd_list():
      self.cl.init_cmd(cmd)
    self.assertEqual(self.cl.cmds, {'hurble': self.test_cmd})

  def test_has_cmd(self):
    self.init_cl()

    hurble_result = self.cl.has_cmd('hurble')
    burble_result = self.cl.has_cmd('burble')

    self.assertEqual(hurble_result, True)
    self.assertEqual(burble_result, False)

  
  def test_get_cmd(self):
    self.init_cl()

    hurble_result = self.cl.get_cmd('hurble')
    self.assertEqual(hurble_result, self.test_cmd)

  def test_get_cmd_err(self):
    with self.assertRaises(ValueError):
      self.init_cl()

      burble_result = self.cl.get_cmd('burble')


