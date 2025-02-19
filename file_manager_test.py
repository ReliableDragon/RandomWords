import unittest
import pathlib
import tempfile
import logging
import random

from unittest.mock import MagicMock, patch, mock_open

import file_manager
from file_manager import FileManager

logger = logging.getLogger(__name__)

WORD_DATA = '''apple
bagel
calzone
'''

def make_mock_file(filename, suffix='.txt', is_dir=False):
    mock_file_object = MagicMock(spec=pathlib.Path)
    mock_file_object.__str__.return_value = filename
    mock_file_object.name = filename
    mock_file_object.suffix = suffix
    mock_file_object.is_dir.return_value = is_dir
    return mock_file_object

class FileManagerTest(unittest.TestCase):

  def test_get_path(self):
    fm = FileManager('one', 'two.txt')
    self.assertEqual(fm.get_path(), 'one/two.txt')

  def test_cd_root(self):
    fm = FileManager('dir', 'file.txt')
    fm.cd('/')
    self.assertEqual(file_manager.ROOT_DIR, fm.dir)

  def test_cd_dd(self):
    fm = FileManager('dir/sub', 'file.txt')
    fm.cd('..')
    self.assertEqual('dir/', fm.dir)

  def test_cd_dd_root(self):
    fm = FileManager()
    fm.cd('..')
    self.assertEqual(file_manager.ROOT_DIR, fm.dir)

  def test_cd_sub(self):
    fm = FileManager('dir', 'file.txt')
    fm.cd('sub')
    self.assertEqual('dir/sub/', fm.dir)

  @patch('builtins.open', new_callable=mock_open, read_data=WORD_DATA)
  def test_get_words(self, mock_file):
    fm = FileManager('testdir', 'test.txt')
    self.assertCountEqual(fm.get_words(), ['apple', 'bagel', 'calzone'])
    mock_file.assert_called_with('testdir/test.txt')
   
  @patch('pathlib.Path.iterdir')
  def test_ls(self, mock_iterdir):
    folder = make_mock_file('testfolder', '', True)
    hidden_folder = make_mock_file('.git', '', True)
    txt_file = make_mock_file('testdict')
    nontxt_file = make_mock_file('testimg', 'jpg')

    mock_path_objects = [folder, hidden_folder, txt_file, nontxt_file] 
    mock_iterdir.return_value = mock_path_objects

    fm = FileManager('testdir')
    results = fm.ls()

    self.assertCountEqual(results, [folder, txt_file])
    mock_iterdir.assert_called_once()


  def test_get_txts(self):
    with (
      tempfile.TemporaryDirectory() as d1,
      tempfile.NamedTemporaryFile(suffix='.txt', dir=d1+'/') as tf1,
      tempfile.NamedTemporaryFile(suffix='.jpeg', dir=d1) as ntf1,
      tempfile.TemporaryDirectory(dir=d1) as d2,
      tempfile.NamedTemporaryFile(suffix='.txt', dir=d1) as tf2,
      tempfile.NamedTemporaryFile(suffix='.jpeg', dir=d1) as ntf2,
    ):
      fm = FileManager(d1)
      txts = fm.get_txts()
      self.assertCountEqual(txts, [tf1.name, tf2.name])
      
  @patch('random.choice')
  def test_rand_dir(self, mock_choice):
    fm = FileManager('initial', 'test.txt')
    dd1 = make_mock_file('subdir', '', True)
    df1 = make_mock_file('test.txt')
    dd2 = make_mock_file('subsubdir', '', True)
    df2 = make_mock_file('test2.txt')
    dd3 = make_mock_file('subsubsubdir', '', True)
    df3 = make_mock_file('test3.txt')
    fm.ls = MagicMock(side_effect=([[dd1, df1], [dd2, df2], [dd3, df3]]))
    mock_choice.side_effect = [dd1, dd2, df3] 

    result = fm.rand_dir()

    self.assertEqual(fm.dir, 'initial')
    self.assertEqual(result, 'test3.txt')

