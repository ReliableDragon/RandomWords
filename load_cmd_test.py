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

  def test_matches(self):
    fm = MagicMock(spec=FileManager)
    
    load = Load(fm)
    result = load.matches('test.txt')

    self.assertEqual(result, True)
