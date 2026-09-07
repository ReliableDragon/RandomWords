import unittest

from unittest.mock import MagicMock

from fake_file_manager import FakeFileManager
from intersection_cmd import Intersection

class IntersectionCommandTest(unittest.TestCase):

  def test_matches(self):
    al = Intersection(MagicMock())
    self.assertTrue(al.matches('i d f.txt'))
    self.assertTrue(al.matches('intersection asdf_asdf qwery/qwerty/qwerty.txt'))
    self.assertTrue(al.matches('i one two three'))
    self.assertTrue(al.matches('i bb'))
    self.assertTrue(al.matches('i aa/bb/cc.txt'))
    self.assertFalse(al.matches('i one two three four'))

  def test_parse_args(self):
    al = Intersection(MagicMock())
    self.assertEqual(al.parse_args('i a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('i one two three'), ['one', 'two', 'three'])

  def test_execute(self):
    with FakeFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertIn('spenoik', result.updates)
      self.assertCountEqual(result.updates['spenoik'], ['b', 'c'])

  def test_execute_three_arg(self):
    with FakeFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertIn('dilau', result.updates)
      self.assertCountEqual(result.updates['dilau'], ['b', 'c'])

  def test_execute_two_aliases(self):
    with FakeFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertIn('blizztu', result.updates)
      self.assertCountEqual(result.updates['blizztu'], ['3'])

  def test_execute_two_files_rooting(self):
    with FakeFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute([tfm.td.tf1_name, tfm.td.tf5_path, 'erbint'], {})
      self.assertIn('erbint', result.updates)
      self.assertCountEqual(result.updates['erbint'], [])

  def test_execute_bad_file(self):
    with FakeFileManager() as tfm:
      al = Intersection(tfm)
      context = {'pleebex': ['a', 'b', 'c']}
      result = al.execute(['pleebex', 'bad_file.txt', 'erbint'], context)
      self.assertFalse(result.updates)
      self.assertCountEqual(context['pleebex'], ['a', 'b', 'c'])
      self.assertFalse(result.ok)
      self.assertEqual(result.message, 'Invalid filename: bad_file.txt')

  def test_execute_two_args_err(self):
    # With two arguments the result is written back to the first one, so a
    # first argument that is not a saved pool is a user error, not a crash.
    with FakeFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute([tfm.td.tf5_path, tfm.td.tf1_name], {})
      self.assertFalse(result.ok)
    self.assertIn('is not a saved pool', result.message)
