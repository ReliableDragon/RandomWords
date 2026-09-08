import unittest
from command_manager import CommandManager

from unittest.mock import MagicMock, patch

from command_list import CommandList
from parser import Parser, unknown_command_result
from command import Command
from fake_command import FakeCommand
from file_manager import FileManager

# Every syntax the tool documents, and the command each one must resolve to.
# Shared with the parity test in web_parity_test.py, which drives the same
# table through the HTTP layer.
DOCUMENTED_SYNTAXES = [
  ('ls', 'ls'), ('ls myth', 'ls'), ('ls myth/greek', 'ls'),
  ('load a.txt', 'load'), ('load alias', 'load'),
  ('a/b.txt', 'load'), ('LOAD a.txt', 'load'),
  ('', 'get_word'), ('word', 'get_word'), ('next', 'get_word'),
  ('5', 'get_word'),
  ('r', 'load_rand_file'), ('rand myth', 'load_rand_file'),
  ('random', 'load_rand_file'),
  ('dr', 'load_rand_dir_file'), ('dir_random', 'load_rand_dir_file'),
  ('al foo', 'alias_load'), ('alias foo a.txt', 'alias_load'),
  ('save foo', 'save'), ('save foo bar', 'save'),
  ('gaw foo bar', 'get_alias_words'),
  ('help', 'help'),
  ('mul myth war', 'multi_folder_get_words'),
  ('c a b', 'combine'), ('d a b', 'diff'), ('i a b', 'intersection'),
  ('rd', 'rand_diff'), ('rd 450', 'rand_diff'),
  ('dump', 'dump'), ('dump all', 'dump'),
  ('quit', 'quit'), ('exit', 'quit'), ('q', 'quit'),
  ('forget spare', 'forget'), ('rm spare', 'forget'),
  ('which whale', 'which'),
  ('rare', 'rare'), ('rare 3', 'rare'),
  ('like whale', 'like'), ('like whale 5', 'like'),
]


class ParserTest(unittest.TestCase):

  def make_mock_command(self):
    mock_command = MagicMock(spec=Command)
    mock_command.name = 'cd'
    mock_command.matches.side_effect = lambda a: a.startswith('cd')
    mock_command.parse_args.side_effect = lambda a: a.split(' ')[1:]
    return mock_command

  def setUp(self):
    self.test_cmd = FakeCommand()
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

  def test_parse_every_documented_syntax(self):
    """Commands are tried in registration order; this pins the precedence."""
    cl = CommandList(FileManager())
    CommandManager(cl).initialize_commands()
    par = Parser(cl)

    cases = DOCUMENTED_SYNTAXES
    for line, expected in cases:
      with self.subTest(line=line):
        cmd, _ = par.parse(line)
        self.assertIsNotNone(cmd, f'{line!r} matched no command')
        self.assertEqual(cmd.name, expected)

  def test_parse_strips_surrounding_whitespace(self):
    cl = CommandList(FileManager())
    CommandManager(cl).initialize_commands()
    par = Parser(cl)

    cmd, args_ = par.parse('  load a.txt  ')
    self.assertEqual(cmd.name, 'load')
    self.assertEqual(args_, ['a.txt'])

  @patch('builtins.input', lambda *args: 'zzz not a command')
  def test_get_command_unresolved(self):
    self.assertEqual(self.par.get_command(), (None, []))

  def test_unknown_command_result(self):
    result = unknown_command_result()
    self.assertFalse(result.ok)
    self.assertEqual(result.message, "I'm sorry, I don't understand.")
