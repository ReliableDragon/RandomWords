import unittest
import os

from unittest.mock import patch

from fake_file_manager import FakeFileManager
from load_rand_file_cmd import LoadRandFile

class LoadRandFileTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]

    with FakeFileManager() as tfm:
      lrf = LoadRandFile(tfm)
      result = lrf.execute([], None)

      self.assertTrue('words' in result.updates)
      self.assertCountEqual(result.updates['words'], ['one', 'two', 'three'])

  def test_execute_empty_folder(self):
    with FakeFileManager() as tfm:
      empty = os.path.join(tfm.td.root, 'empty')
      os.mkdir(empty)
      lrf = LoadRandFile(tfm)

      result = lrf.execute([tfm.td.rel(empty)], None)
      self.assertFalse(result.ok)
    self.assertIn('No .txt files found', result.message)
