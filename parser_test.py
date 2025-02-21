import unittest

from unittest.mock import MagicMock, patch

from command_list import CommandList
from parser import Parser
from command import Command

class ParserTest(unittest.TestCase):

  def make_mock_command(self):
    mock_command = MagicMock(spec=Command)
    mock_command.name = 'cd'
    mock_command.matches.side_effect = lambda a: a.startswith('cd')
    mock_command.parse_args.side_effect = lambda a: a.split(' ')[1:]
    return mock_command

  @patch('builtins.input', lambda *args: 'pooble')
  @patch.object(Parser, 'parse')
  def test_get_command(self, mock_parse):
    cl = MagicMock(spec=CommandList)
    mock_command = MagicMock(spec=Command)
    mock_args = ['a', 'b', 'c']
    mock_parse.return_value = (mock_command, mock_args)
    parser = Parser(cl)

    result = parser.get_command()
    self.assertEqual(result, (mock_command, mock_args))
    mock_parse.assert_called_once_with('pooble')

  def test_parse(self):
    mock_command = self.make_mock_command()

    cl = MagicMock(spec=CommandList)
    cl.cmds = {'cd': mock_command}
    
    parser = Parser(cl)
    results = parser.parse('cd a/b/c')

    self.assertEqual(results, (mock_command, ['a/b/c']))


  def test_parse_err(self):
    mock_command = self.make_mock_command()

    cl = MagicMock(spec=CommandList)
    cl.cmds = {'cd': mock_command}
    
    parser = Parser(cl)
    results = parser.parse('ls a/b/c')

    self.assertEqual(results, (None, []))
