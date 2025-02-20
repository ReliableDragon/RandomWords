import unittest

from command import Command
from arg import Arg

class TestCommand(unittest.TestCase):


  def test_str(self):
    arg = Arg(int)
    cmd = Command.create('phloub', [arg])
    self.assertEqual(str(cmd), "Command(phloub)['Arg()[int]: None']")

  def test_validate_args(self):
    cmd = Command.create('fleebnorp', [int, str])
    values = [1, 'two']
    cmd.validate_args(values)

  def test_bad_len_populate(self):
    intarg = Arg(int)
    cmd = Command.create('shneeble', [int, int])
    with self.assertRaises(ValueError):
      cmd.validate_args([1, 2, 3])

  def test_bad_type_populate(self):
    intarg = Arg(int)
    cmd = Command.create('shneeble', [int, int, str])
    with self.assertRaises(ValueError):
      cmd.validate_args([1, 2, 3])
