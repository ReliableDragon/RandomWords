import unittest
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from file_manager import FileManager
from test_file_manager import TestFileManager
from load_rand_file_cmd import LoadRandFile

# TODO: Actually test the right thing.
class RandDiffTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]
    f = io.StringIO()

    with (TestFileManager() as tfm,
      redirect_stdout(f)):
      pass
