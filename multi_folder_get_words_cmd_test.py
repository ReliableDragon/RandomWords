import unittest
import os

from unittest.mock import patch

from multi_folder_get_words_cmd import MultiFolderGetWords
from fake_file_manager import FakeFileManager

class MultiFolderGetWordsTest(unittest.TestCase):

  def test_matches(self):
    with FakeFileManager() as tfm:
      mfgw = MultiFolderGetWords(tfm)
      self.assertTrue(mfgw.matches('mfgw dragon/blood newt/eye virgin/tear'))
      self.assertTrue(mfgw.matches('mul a_b'))
      self.assertTrue(mfgw.matches('multi_folder_get_words 1 2 3'))
      self.assertFalse(mfgw.matches('mul'))

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[0]
    with FakeFileManager() as tfm:
      mfgw = MultiFolderGetWords(tfm)
      args_ = [tfm.td.d3.name, tfm.td.d4.name]
      result = mfgw.execute(args_, {})
    self.assertEqual(result.message, 'aeschylinux five')

  @patch('random.choice')
  def test_execute_with_context(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[0]
    with FakeFileManager() as tfm:
      mfgw = MultiFolderGetWords(tfm)
      args_ = ['thlong', tfm.td.d4.name]
      result = mfgw.execute(args_, {'thlong': ['neeble']})
    self.assertEqual(result.message, 'neeble five')

  @patch('random.choice')
  def test_execute_with_file(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[0]
    with FakeFileManager() as tfm:
      mfgw = MultiFolderGetWords(tfm)
      args_ = [tfm.td.tf1.name, tfm.td.d4.name]
      result = mfgw.execute(args_, {})
    self.assertEqual(result.message, 'a five')

  @patch('random.choice')
  def test_execute_with_rel_dirs(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[0]
    with FakeFileManager() as tfm:
      tfm.dir = tfm.td.d2.name
      mfgw = MultiFolderGetWords(tfm)
      args_ = [tfm.td.d3_name, tfm.td.d4_name]
      result = mfgw.execute(args_, {})
    self.assertEqual(result.message, 'aeschylinux five')

  def test_execute_empty_folder(self):
    with FakeFileManager() as tfm:
      empty = os.path.join(tfm.td.root, 'empty')
      os.mkdir(empty)
      mfgw = MultiFolderGetWords(tfm)

      result = mfgw.execute([empty], {})
      self.assertFalse(result.ok)
    self.assertIn('No .txt files found', result.message)
