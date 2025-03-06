import unittest

from unittest.mock import MagicMock

from test_file_manager import TestFileManager
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
    with TestFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertTrue('spenoik' in result)
      self.assertCountEqual(result['spenoik'], ['a', 'b', 'c', 'd'])

  def test_execute_three_arg(self):
    with TestFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertTrue('dilau' in result)
      self.assertCountEqual(result['dilau'], ['a', 'b', 'c', 'd'])

  def test_execute_two_aliases(self):
    with TestFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertTrue('blizztu' in result)
      self.assertCountEqual(result['blizztu'], ['1', '2', '3', '4', '5'])

  def test_execute_two_files(self):
    with TestFileManager() as tfm:
      al = Combine(tfm)
      result = al.execute([tfm.td.tf5.name, tfm.td.tf1_name, 'erbint'], {})
      self.assertTrue('erbint' in result)
      self.assertCountEqual(result['erbint'], ['a', 'b', 'c', 'five'])

  def test_execute_two_args_err(self):
    with TestFileManager() as tfm:
      al = Combine(tfm)
      with self.assertRaises(AssertionError):
        result = al.execute([tfm.td.tf5.name, tfm.td.tf1_name], {})
