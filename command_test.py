import unittest

from arg import Arg
from command import Command

class TestCommand(unittest.TestCase):


  def test_str(self):
    cmd = Command.create('phloub', []) 
    self.assertEqual(str(cmd), "Command(phloub)[]")

  def test_validate_args(self):
    cmd = Command.create('fleebnorp', [Arg(int), Arg(str)])
    values = [1, 'two']
    cmd.validate_args(values)

  def test_bad_len_populate(self):
    cmd = Command.create('shneeble', [Arg(int), Arg(int)])
    with self.assertRaises(ValueError):
      cmd.validate_args([1, 2, 3])

  def test_bad_type_populate(self):
    cmd = Command.create('shneeble', [Arg(int), Arg(int), Arg(str)])
    with self.assertRaises(ValueError):
      cmd.validate_args([1, 2, 3])

  def test_parse_args_no_args(self):
    cmd = Command.create('vordii', [])
    args_ = cmd.parse_args('aaaaaaa')
    self.assertFalse(args_)

  def test_get_one_arg(self):
    cmd = Command.create('woogle', [Arg(int)])
    args_ = cmd.parse_args('a b')
    self.assertEqual(args_, ['b'])
    
  def test_parse_args(self):
    cmd = Command.create('woogle_two', [Arg(int)])
    args_ = cmd.parse_args('a b c')
    self.assertEqual(args_, ['b', 'c'])

  def test_matches_true(self):
    cmd = Command.create('bubbub', [Arg(int)])
    result = cmd.matches('bubbub 123')
    self.assertEqual(result, True)

  def test_matches_false(self):
    cmd = Command.create('bubbub', [Arg(int)])
    result = cmd.matches('ciccic 123')
    self.assertEqual(result, False)
