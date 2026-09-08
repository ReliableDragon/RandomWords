import unittest

from command import Command

class TestCommand(unittest.TestCase):

  # validate_args and its tests are gone along with Arg: the base class no
  # longer carries a typed argument description to validate against. The
  # matches() tests below take over the job of pinning down what a plain
  # Command actually accepts.

  def test_str(self):
    cmd = Command.create('phloub')
    self.assertEqual(str(cmd), "Command(phloub)")

  def test_parse_args_no_args(self):
    cmd = Command.create('vordii')
    args_ = cmd.parse_args('vordii')
    self.assertFalse(args_)

  def test_get_one_arg(self):
    cmd = Command.create('woogle')
    args_ = cmd.parse_args('woogle b')
    self.assertEqual(args_, ['b'])

  def test_parse_args(self):
    cmd = Command.create('woogle_two')
    args_ = cmd.parse_args('woogle_two b c')
    self.assertEqual(args_, ['b', 'c'])

  def test_parse_args_strips_the_line(self):
    cmd = Command.create('woogle')
    self.assertEqual(cmd.parse_args('  woogle b  '), ['b'])

  # The default matches() only accepts the bare command word: it has no
  # argument description left to build a richer regex from, so a command
  # with a real syntax has to say so itself, in its own matches().
  def test_matches_true(self):
    cmd = Command.create('bubbub')
    self.assertTrue(cmd.matches('bubbub'))
    self.assertTrue(cmd.matches('BUBBUB'))

  def test_matches_false(self):
    cmd = Command.create('bubbub')
    self.assertFalse(cmd.matches('ciccic'))
    self.assertFalse(cmd.matches('bubbub 123'))

  def test_default_overview_is_the_bare_command_word(self):
    cmd = Command.create('vordii')
    self.assertEqual(cmd.overview(), 'vordii')
