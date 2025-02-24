import unittest

from unittest.mock import MagicMock, patch

from command_list import CommandList
from parser import Parser
from command import Command
from test_command import TestCommand
from file_manager import FileManager

class ParserTest(unittest.TestCase):

  def make_mock_command(self):
    mock_command = MagicMock(spec=Command)
    mock_command.name = 'cd'
    mock_command.matches.side_effect = lambda a: a.startswith('cd')
    mock_command.parse_args.side_effect = lambda a: a.split(' ')[1:]
    return mock_command

  def setUp(self):
    self.test_cmd = TestCommand()
    self.test_cmd.name = 'pooble'
    
    self.fm = FileManager()
    self.cl = CommandList(self.fm)
    self.par = Parser(self.cl)
    
    self.orig_cmd_list = self.cl.cmd_list
    self.cl.cmd_list = MagicMock(return_value=[self.test_cmd])
    self.cl.init_cmd(self.test_cmd)

  @patch('builtins.input', lambda *args: 'pooble ten 10')
  def test_get_command(self):
    result = self.par.get_command()
    self.assertEqual(result, (self.test_cmd, ['ten', '10']))

  def test_parse(self):
    results = self.par.parse('pooble a/b/c')

    self.assertEqual(results, (self.test_cmd, ['a/b/c']))


  def test_parse_err(self):
    results = self.par.parse('ls a/b/c')

    self.assertEqual(results, (None, []))
