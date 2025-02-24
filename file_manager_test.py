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
    self.assertCountEqual(fm.get_words('testdir/test.txt'), ['apple', 'bagel', 'calzone'])
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
      tempfile.NamedTemporaryFile(suffix='.txt', dir=d2) as tf2,
      tempfile.NamedTemporaryFile(suffix='.jpeg', dir=d2) as ntf2,
    ):
      fm = FileManager(d1)
      txts = fm.get_txts()
      self.assertCountEqual(txts, [tf1.name, tf2.name])

  @patch('random.choice')
  def test_rand_file(self, mock_choice):
    with (
      tempfile.TemporaryDirectory() as d1,
      tempfile.NamedTemporaryFile(suffix='.txt', prefix='z', dir=d1+'/') as tf1,
      tempfile.NamedTemporaryFile(suffix='.jpeg', prefix='a', dir=d1) as ntf1,
      tempfile.TemporaryDirectory(prefix='m', dir=d1) as d2,
      tempfile.NamedTemporaryFile(suffix='.txt', prefix='z', dir=d2) as tf2,
      tempfile.NamedTemporaryFile(suffix='.jpeg', prefix='a', dir=d2) as ntf2,
    ):
      mock_choice.side_effect = lambda a: sorted(a)[0]

      fm = FileManager(d1)
      result = fm.rand_file()

      self.assertEqual(result, tf2.name)
    
      
  @patch('random.choice')
  def test_rand_dir(self, mock_choice):
    with (
      tempfile.TemporaryDirectory() as d1,
      tempfile.TemporaryDirectory(prefix='a', dir=d1) as d2,
      tempfile.NamedTemporaryFile(suffix='.txt', prefix='z', dir=d1) as tf1,
      tempfile.TemporaryDirectory(prefix='a', dir=d2) as d3,
      tempfile.NamedTemporaryFile(suffix='.txt', prefix='z', dir=d2) as tf2,
      tempfile.NamedTemporaryFile(suffix='.txt', prefix='a', dir=d3) as tf4,
      tempfile.NamedTemporaryFile(suffix='.txt', prefix='z', dir=d3) as tf3,
    ):
      mock_choice.side_effect = lambda a: sorted(a)[0]

      fm = FileManager(d1)
      result = fm.rand_dir()

      self.assertEqual(fm.dir, d1)
      self.assertEqual(result, tf4.name)

