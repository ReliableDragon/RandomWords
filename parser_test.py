import unittest

from unittest.mock import MagicMock, patch

from command_list import CommandList
from parser import Parser
from command import Command

class ParserTest(unittest.TestCase):

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
    cl = MagicMock(spec=CommandList)
    mock_command = MagicMock(spec=Command)
    cl.has_cmd.return_value = True
    cl.get_cmd.return_value = mock_command
    parser = Parser(cl)
  
    results = parser.parse('cd a/b/c')

    self.assertEqual(results, (mock_command, ['a/b/c']))
    cl.has_cmd.assert_called_once_with('cd')
    cl.get_cmd.assert_called_once_with('cd')


  def test_parse_err(self):
    cl = MagicMock(spec=CommandList)
    mock_command = MagicMock(spec=Command)
    cl.has_cmd.return_value = False
    cl.get_cmd.return_value = mock_command
    parser = Parser(cl)
 
    results = parser.parse('cd a/b/c')

    self.assertEqual(results, (None, []))
    cl.has_cmd.assert_called_once_with('cd')
    cl.get_cmd.assert_not_called()
