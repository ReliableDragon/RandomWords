import unittest

from arg import Arg

class TestArg(unittest.TestCase):


  def test_init(self):
    arg = Arg(int, 3, "three")
    self.assertEqual(str(arg), "Arg(three)[int]: 3")

  def test_populate(self):
    arg = Arg(str)
    arg.populate("test")
    self.assertEqual(str(arg), "Arg()[str]: test")

  def test_get(self):
    arg = Arg(float, 1.0)
    self.assertEqual(arg.get(), 1.0)

  def test_list(self):
    arg = Arg(list, [1, 2, 3])
    self.assertEqual(arg.get(), [1, 2, 3])

  def test_dict(self):
    arg = Arg(dict, {1: 'a'})
    self.assertEqual(arg.get(), {1: 'a'})

  def test_invalid_type(self):
    arg = Arg(int)
    with self.assertRaises(ValueError):
      arg.populate('s')
