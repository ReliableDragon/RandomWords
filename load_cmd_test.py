import unittest
from contextlib import redirect_stdout
import io

from unittest.mock import MagicMock

from load_cmd import Load
from file_manager import FileManager
from fake_file_manager import FakeFileManager

class LoadTest(unittest.TestCase):

  def test_execute(self):
    with FakeFileManager() as tfm:
      load = Load(tfm)
      result = load.execute([tfm.td.tf1.name], {})

      self.assertTrue('words' in result.updates)
      self.assertCountEqual(result.updates['words'], ['a', 'b', 'c'])
      self.assertEqual(result.data, {'size': 3})

  def test_execute_context(self):
    with FakeFileManager() as tfm:
      load = Load(tfm)
      result = load.execute(['yanoo'], {'yanoo': ['1', '2', '3']})

      self.assertTrue('words' in result.updates)
      self.assertCountEqual(result.updates['words'], ['1', '2', '3'])

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

  def test_parse_args_is_case_insensitive(self):
    l = Load(MagicMock(spec=FileManager))
    self.assertEqual(l.parse_args('LOAD shmeeble'), ['shmeeble'])
    self.assertEqual(l.parse_args('Load a/b/C.txt'), ['a/b/C.txt'])

  def test_execute_missing_file_keeps_pool(self):
    # FileManager.get_words still prints its own diagnostic directly; that
    # is unrelated to Load's own message and stays on stdout.
    f = io.StringIO()
    with (FakeFileManager() as tfm,
      redirect_stdout(f)):
      load = Load(tfm)
      result = load.execute(['nope.txt'], {})
    self.assertIn('Invalid filename', f.getvalue())
    self.assertFalse(result.ok)
    self.assertEqual(result.message, 'No words found in nope.txt; keeping the current pool.')

  def test_execute_unknown_alias_keeps_pool(self):
    with FakeFileManager() as tfm:
      load = Load(tfm)
      result = load.execute(['nope'], {'words': ['a']})
    self.assertFalse(result.ok)
    self.assertIn('valid values are', result.message)
