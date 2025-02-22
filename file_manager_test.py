import unittest
import pathlib
import tempfile
import logging
import random

from unittest.mock import MagicMock, patch, mock_open

import file_manager
import test_util
from file_manager import FileManager
from test_util import make_mock_file

logger = logging.getLogger(__name__)

WORD_DATA = '''apple
bagel
calzone
'''

class FileManagerTest(unittest.TestCase):

  def test_cd_root(self):
    fm = FileManager('dir')
    fm.cd('/')
    self.assertEqual(file_manager.ROOT_DIR, fm.dir)

  def test_cd_dd(self):
    fm = FileManager('dir/sub')
    fm.cd('..')
    self.assertEqual('dir/', fm.dir)

  def test_cd_dd_root(self):
    fm = FileManager()
    fm.cd('..')
    self.assertEqual(file_manager.ROOT_DIR, fm.dir)

  def test_cd_sub(self):
    fm = FileManager('dir')
    fm.cd('sub')
    self.assertEqual('dir/sub/', fm.dir)

  @patch('builtins.open', new_callable=mock_open, read_data=WORD_DATA)
  def test_get_words(self, mock_file):
    fm = FileManager('testdir')
    self.assertCountEqual(fm.get_words('test.txt'), ['apple', 'bagel', 'calzone'])
    mock_file.assert_called_with('testdir/test.txt')
   
  @patch('pathlib.Path.iterdir')
  def test_ls(self, mock_iterdir):
    mock_path_objects = test_util.get_mock_files()
    folder, _, txt_file, _ = mock_path_objects
    mock_iterdir.return_value = mock_path_objects

    fm = FileManager('testdir')
    results = fm.ls()

    self.assertCountEqual(results, [folder, txt_file])
    mock_iterdir.assert_called_once()

  def test_ls_not_found(self):
    with self.assertRaises(FileNotFoundError):
      fm = FileManager('shmeeble')
      results = fm.ls()

  # TODO: This is not a good test.
  def test_ls_with_arg(self):
    mock_path = MagicMock(spec=pathlib.Path)
    mock_path_objects = test_util.get_mock_files()
    folder, _, txt_file, _ = mock_path_objects
    mock_path.iterdir.return_value = mock_path_objects

    def check_path(fn):
      if fn == 'testdir/':
        return mock_path
      return None

    with patch.object(pathlib, 'Path', side_effect=check_path):
      fm = FileManager('shmeeble')
      results = fm.ls('testdir/')

    self.assertCountEqual(results, [folder, txt_file])
    mock_path.iterdir.assert_called_once()

  def test_ls_with_arg_not_found(self):
    with self.assertRaises(FileNotFoundError):
      fm = FileManager('shmeeble')
      results = fm.ls('bad_folder/')

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
  @patch('pathlib.Path.rglob')
  def test_rand_file(self, mock_rglob, mock_choice):
    mock_rglob.return_value = ['a.txt', 'b.txt', 'c.txt']
    mock_choice.side_effect = lambda a: a[0]

    fm = FileManager('initial/')
    result = fm.rand_file()

    self.assertEqual(result, 'a.txt')
    
      
  @patch('random.choice')
  def test_rand_dir(self, mock_choice):
    fm = FileManager('initial')
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
    self.assertEqual(result, 'initial/subdir/subsubdir/test3.txt')

