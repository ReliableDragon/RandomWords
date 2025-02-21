import unittest

from unittest.mock import MagicMock

from load_cmd import Load
from file_manager import FileManager

class LoadTest(unittest.TestCase):

  def test_execute(self):
    fm = MagicMock(spec=FileManager)
    fm.get_words.return_value = ['a', 'b', 'c']

    load = Load(fm)
    result = load.execute(['test.txt'], {})

    self.assertEqual(result, {'words': ['a', 'b', 'c']})

  def test_matches(self):
    fm = MagicMock(spec=FileManager)
    
    load = Load(fm)
    result = load.matches('test.txt')

    self.assertEqual(result, True)
