import unittest

from arg import Arg

class TestArg(unittest.TestCase):


  def test_init(self):
    arg = Arg(int)
    self.assertEqual(str(arg), "Arg[int](optional: False)")

  def test_validate(self):
    arg = Arg(int)
    self.assertFalse(arg.validate(1.0))
    self.assertTrue(arg.validate(3))
    self.assertFalse(arg.validate("1"))
    self.assertFalse(arg.validate(None))

  def test_optional_validate(self):
    arg = Arg(bool, optional=True)
    self.assertTrue(arg.validate(True))
    self.assertFalse(arg.validate(1))
    self.assertFalse(arg.validate("True"))
    self.assertTrue(arg.validate(None))
