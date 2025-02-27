import unittest

from unittest.mock import MagicMock

from test_file_manager import TestFileManager
from diff_cmd import Diff

class DiffCommandTest(unittest.TestCase):

  def test_matches(self):
    al = Diff(MagicMock())
    self.assertTrue(al.matches('d d f.txt'))
    self.assertTrue(al.matches('diff asdf_asdf qwery/qwerty/qwerty.txt'))
    self.assertTrue(al.matches('d one two three'))
    self.assertFalse(al.matches('d bb'))
    self.assertFalse(al.matches('d aa/bb/cc.txt'))
    self.assertFalse(al.matches('d one two three four'))

  def test_parse_args(self):
    al = Diff(MagicMock())
    self.assertEqual(al.parse_args('d a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('d one two three'), ['one', 'two', 'three'])

  def test_execute(self):
    with TestFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertTrue('spenoik' in result)
      self.assertCountEqual(result['spenoik'], ['d'])

  def test_execute_three_arg(self):
    with TestFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertTrue('dilau' in result)
      self.assertCountEqual(result['dilau'], ['d'])

  def test_execute_two_aliases(self):
    with TestFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertTrue('blizztu' in result)
      self.assertCountEqual(result['blizztu'], ['1', '2'])

  def test_execute_two_files_rooting(self):
    with TestFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute([tfm.td.tf1_name, tfm.td.tf5.name, 'erbint'], {})
      self.assertTrue('erbint' in result)
      self.assertCountEqual(result['erbint'], ['a', 'b', 'c'])

  def test_execute_two_args_err(self):
    with TestFileManager() as tfm:
      al = Diff(tfm)
      with self.assertRaises(AssertionError):
        result = al.execute([tfm.td.tf5.name, tfm.td.tf1_name], {})
