import unittest
import random
import io

from contextlib import redirect_stdout
from unittest.mock import patch

from multi_folder_get_words_cmd import MultiFolderGetWords
from test_file_manager import TestFileManager

class MultiFolderGetWordsTest(unittest.TestCase):

  def test_matches(self):
    with TestFileManager() as tfm:
      mfgw = MultiFolderGetWords(tfm)
      self.assertTrue(mfgw.matches('mfgw dragon/blood newt/eye virgin/tear')) 
      self.assertTrue(mfgw.matches('mul a_b'))
      self.assertTrue(mfgw.matches('multi_folder_get_words 1 2 3'))
      self.assertFalse(mfgw.matches('mul'))

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: a[0]
    f = io.StringIO()
    with (TestFileManager() as tfm,
      redirect_stdout(f)):
      mfgw = MultiFolderGetWords(tfm)
      args_ = [tfm.td.d3.name, tfm.td.d4.name]
      mfgw.execute(args_, {})
    self.assertEqual(f.getvalue(), 'aeschylinux five\n')

  @patch('random.choice')
  def test_execute_with_rel_dirs(self, mock_choice):
    mock_choice.side_effect = lambda a: a[0]
    f = io.StringIO()
    with (TestFileManager() as tfm,
      redirect_stdout(f)):
      tfm.dir = tfm.td.d2.name
      mfgw = MultiFolderGetWords(tfm)
      args_ = [tfm.td.d3_name, tfm.td.d4_name]
      mfgw.execute(args_, {})
    self.assertEqual(f.getvalue(), 'aeschylinux five\n')

