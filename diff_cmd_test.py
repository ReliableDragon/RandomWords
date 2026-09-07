import unittest

from unittest.mock import MagicMock

from fake_file_manager import FakeFileManager
from diff_cmd import Diff

class DiffCommandTest(unittest.TestCase):

  def test_matches(self):
    al = Diff(MagicMock())
    self.assertTrue(al.matches('d d f.txt'))
    self.assertTrue(al.matches('diff asdf_asdf qwery/qwerty/qwerty.txt'))
    self.assertTrue(al.matches('d one two three'))
    self.assertTrue(al.matches('d bb'))
    self.assertFalse(al.matches('d'))
    self.assertTrue(al.matches('d aa/bb/cc.txt'))
    self.assertFalse(al.matches('d one two three four'))

  def test_parse_args(self):
    al = Diff(MagicMock())
    self.assertEqual(al.parse_args('d a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('d one two three'), ['one', 'two', 'three'])

  def test_execute(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertIn('spenoik', result.updates)
      self.assertCountEqual(result.updates['spenoik'], ['d'])

  def test_execute_three_arg(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertIn('dilau', result.updates)
      self.assertCountEqual(result.updates['dilau'], ['d'])

  def test_execute_two_aliases(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertIn('blizztu', result.updates)
      self.assertCountEqual(result.updates['blizztu'], ['1', '2'])

  def test_execute_two_files_rooting(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute([tfm.td.tf1_name, tfm.td.tf5_path, 'erbint'], {})
      self.assertIn('erbint', result.updates)
      self.assertCountEqual(result.updates['erbint'], ['a', 'b', 'c'])

  def test_execute_two_args_err(self):
    # With two arguments the result is written back to the first one, so a
    # first argument that is not a saved pool is a user error, not a crash.
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute([tfm.td.tf5_path, tfm.td.tf1_name], {})
      self.assertFalse(result.ok)
    self.assertIn('is not a saved pool', result.message)

  def test_execute_one_arg(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['bleenu'], {'bleenu': ['1', '2', '3'], 'words': ['3', '4', '5']})
      self.assertIn('words', result.updates)
      self.assertCountEqual(result.updates['words'], ['4', '5'])

