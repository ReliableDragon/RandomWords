import unittest

from unittest.mock import MagicMock, patch

from file_manager import FileManager
from test_file_manager import TestFileManager
from load_rand_file_cmd import LoadRandFile

class LoadRandFileTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]

    with TestFileManager() as tfm:

      lrf = LoadRandFile(tfm)
      result = lrf.execute([], None)

      self.assertTrue('words' in result)
      print(result)
      self.assertCountEqual(result['words'], ['1', '2', '3', '4', '5', '6', '7'])
