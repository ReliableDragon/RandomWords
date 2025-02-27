import unittest

from unittest.mock import MagicMock

from load_cmd import Load
from file_manager import FileManager
from test_file_manager import TestFileManager

class LoadTest(unittest.TestCase):

  def test_execute(self):
    with TestFileManager() as tfm:
      load = Load(tfm)
      result = load.execute([tfm.td.tf1.name], {})

      self.assertTrue('words' in result)
      self.assertCountEqual(result['words'], ['a', 'b', 'c'])

  def test_execute_context(self):
    with TestFileManager() as tfm:
      load = Load(tfm)
      result = load.execute(['yanoo'], {'yanoo': ['1', '2', '3']})

      self.assertTrue('words' in result)
      self.assertCountEqual(result['words'], ['1', '2', '3'])

  def test_matches(self):
    fm = MagicMock(spec=FileManager)
    
    load = Load(fm)
    self.assertTrue(load.matches('test.txt'))
    self.assertTrue(load.matches('a/b/c.txt'))
    self.assertTrue(load.matches('load shmeeble'))
    self.assertTrue(load.matches('load a/b/c.txt'))
    self.assertFalse(load.matches('shmeeble'))

  def test_parse_args(self):
    fm = MagicMock(spec=FileManager)

    l = Load(fm)
    self.assertEqual(l.parse_args('test.txt'), ['test.txt'])
    self.assertEqual(l.parse_args('load shmeeble'), ['shmeeble'])
