import unittest

from command import Command
from arg import Arg

class TestCommand(unittest.TestCase):


  def test_init(self):
    arg = Arg(int)
    cmd = Command('phloub', [arg])
    self.assertEqual(str(cmd), "Command(phloub)['Arg()[int]: None']")

  def test_populate_args(self):
    intarg = Arg(int)
    strarg = Arg(str)
    cmd = Command('fleebnorp', [intarg, strarg])
    values = [1, 'two']
    cmd.populate_args(values)
    self.assertEqual(cmd.args[0].value, 1)
    self.assertEqual(cmd.args[1].value, 'two')

  def test_bad_populate(self):
    intarg = Arg(int)
    cmd = Command('shneeble', [intarg])
    with self.assertRaises(ValueError):
      cmd.populate_args([1, 2, 3])
