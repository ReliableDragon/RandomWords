import unittest

from unittest.mock import MagicMock

from fake_file_manager import FakeFileManager
from combine_cmd import Combine

class CombineCmdTest(unittest.TestCase):

  def test_matches(self):
    al = Combine(MagicMock())
    self.assertTrue(al.matches('c d f.txt'))
    self.assertTrue(al.matches('combine asdf_asdf qwery/qwerty/qwerty.txt'))
    self.assertTrue(al.matches('c one two three'))
    self.assertTrue(al.matches('c bb'))
    self.assertTrue(al.matches('c aa/bb/cc.txt'))
    self.assertFalse(al.matches('c one two three four'))

  def test_parse_args(self):
    al = Combine(MagicMock())
    self.assertEqual(al.parse_args('c a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('c one two three'), ['one', 'two', 'three'])

  def test_execute(self):
    with FakeFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertIn('spenoik', result.updates)
      self.assertCountEqual(result.updates['spenoik'], ['a', 'b', 'c', 'd'])

  def test_execute_three_arg(self):
    with FakeFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertIn('dilau', result.updates)
      self.assertCountEqual(result.updates['dilau'], ['a', 'b', 'c', 'd'])

  def test_execute_two_aliases(self):
    with FakeFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertIn('blizztu', result.updates)
      self.assertCountEqual(result.updates['blizztu'], ['1', '2', '3', '4', '5'])

  def test_execute_two_files(self):
    with FakeFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute([tfm.td.tf5.name, tfm.td.tf1_name, 'erbint'], {})
      self.assertIn('erbint', result.updates)
      self.assertCountEqual(result.updates['erbint'], ['a', 'b', 'c', 'five'])

  def test_execute_two_args_err(self):
    # With two arguments the result is written back to the first one, so a
    # first argument that is not a saved pool is a user error, not a crash.
    with FakeFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute([tfm.td.tf5.name, tfm.td.tf1_name], {})
      self.assertFalse(result.ok)
    self.assertIn('is not a saved pool', result.message)
