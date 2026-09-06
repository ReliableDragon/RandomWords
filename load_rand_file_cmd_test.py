import unittest
import os
import io

from contextlib import redirect_stdout
from unittest.mock import patch

from fake_file_manager import FakeFileManager
from load_rand_file_cmd import LoadRandFile

class LoadRandFileTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]
    f = io.StringIO()

    with (FakeFileManager() as tfm,
      redirect_stdout(f)):
      lrf = LoadRandFile(tfm)
      result = lrf.execute([], None)

      self.assertTrue('words' in result)
      self.assertCountEqual(result['words'], ['one', 'two', 'three'])

  def test_execute_empty_folder(self):
    f = io.StringIO()
    with FakeFileManager() as tfm:
      empty = os.path.join(tfm.td.root, 'empty')
      os.mkdir(empty)
      lrf = LoadRandFile(tfm)

      with redirect_stdout(f):
        self.assertIsNone(lrf.execute([empty], None))
    self.assertIn('No .txt files found', f.getvalue())
