import unittest
import logging

from unittest.mock import patch

from fake_file_manager import FakeFileManager
from load_rand_dir_file_cmd import LoadRandDirFile

logger = logging.getLogger(__name__)

class LoadRandFileTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]

    with FakeFileManager() as tfm:
      lrf = LoadRandDirFile(tfm)
      result = lrf.execute([], None)

      self.assertTrue('words' in result.updates)
      self.assertCountEqual(result.updates['words'], ['one', 'two', 'three'])
