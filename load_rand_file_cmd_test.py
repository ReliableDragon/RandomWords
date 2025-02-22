import unittest

from unittest.mock import MagicMock

from file_manager import FileManager
from load_rand_file_cmd import LoadRandFile

class LoadRandFileTest(unittest.TestCase):

  def test_execute(self):
    fm = MagicMock(spec=FileManager)
    fm.rand_file.return_value = 'test.txt'
    fm.get_words.return_value = ['a', 'b', 'c']

    lrf = LoadRandFile(fm)
    result = lrf.execute([], None)

    self.assertEqual(result, {'words': ['a', 'b', 'c']})
    fm.get_words.assert_called_once_with('test.txt')
