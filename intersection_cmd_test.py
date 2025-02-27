import unittest
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock

from test_file_manager import TestFileManager
from intersection_cmd import Intersection

class IntersectionCommandTest(unittest.TestCase):

  def test_matches(self):
    al = Intersection(MagicMock())
    self.assertTrue(al.matches('i d f.txt'))
    self.assertTrue(al.matches('intersection asdf_asdf qwery/qwerty/qwerty.txt'))
    self.assertTrue(al.matches('i one two three'))
    self.assertFalse(al.matches('i bb'))
    self.assertFalse(al.matches('i aa/bb/cc.txt'))
    self.assertFalse(al.matches('i one two three four'))

  def test_parse_args(self):
    al = Intersection(MagicMock())
    self.assertEqual(al.parse_args('i a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('i one two three'), ['one', 'two', 'three'])

  def test_execute(self):
    with TestFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertTrue('spenoik' in result)
      self.assertCountEqual(result['spenoik'], ['b', 'c'])

  def test_execute_three_arg(self):
    with TestFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertTrue('dilau' in result)
      self.assertCountEqual(result['dilau'], ['b', 'c'])

  def test_execute_two_aliases(self):
    with TestFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertTrue('blizztu' in result)
      self.assertCountEqual(result['blizztu'], ['3'])

  def test_execute_two_files_rooting(self):
    with TestFileManager() as tfm:
      al = Intersection(tfm)
      result = al.execute([tfm.td.tf1_name, tfm.td.tf5.name, 'erbint'], {})
      self.assertTrue('erbint' in result)
      self.assertCountEqual(result['erbint'], [])

  def test_execute_bad_file(self):
    f = io.StringIO()
    with (TestFileManager() as tfm,
      redirect_stdout(f)):
      al = Intersection(tfm)
      context = {'pleebex': ['a', 'b', 'c']}
      result = al.execute(['pleebex', 'bad_file.txt', 'erbint'], context)
      self.assertIsNone(result)
      self.assertCountEqual(context['pleebex'], ['a', 'b', 'c'])
      self.assertEqual(f.getvalue(), f'Invalid filename: {tfm.td.root}bad_file.txt\n')

  def test_execute_two_args_err(self):
    with TestFileManager() as tfm:
      al = Intersection(tfm)
      with self.assertRaises(AssertionError):
        result = al.execute([tfm.td.tf5.name, tfm.td.tf1_name], {})
