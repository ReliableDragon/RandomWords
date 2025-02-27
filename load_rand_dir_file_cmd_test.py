import unittest
import os
import logging
import pathlib
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from file_manager import FileManager
from test_file_manager import TestFileManager
from load_rand_dir_file_cmd import LoadRandDirFile

logger = logging.getLogger(__name__)

class LoadRandFileTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]
    f = io.StringIO()

    with (TestFileManager() as tfm,
      redirect_stdout(f)):
        lrf = LoadRandDirFile(tfm)
        result = lrf.execute([], None)

        self.assertTrue('words' in result)
        self.assertCountEqual(result['words'], ['one', 'two', 'three'])
