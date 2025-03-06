import logging
import os
import pathlib
import random
import tempfile
import unittest
import io

from unittest.mock import MagicMock, patch, mock_open
from contextlib import redirect_stdout

import file_manager
import test_util
from file_manager import FileManager
from test_util import make_mock_file
from test_directories import TestDirectories

logger = logging.getLogger(__name__)

WORD_DATA = '''apple
bagel
calzone
'''
GUTENBERG_TXT = '''A header.
*** START OF THE PROJECT GUTENBERG EBOOK KWANGLAP ***
alpontris
*** END OF THE PROJECT GUTENBERG EBOOK KWANGLAP ***
A footer.'''
WORD_SPLIT_TXT = '''one--two
three four*five sïx se—ven ei-ght 9nine9 ten 11 12-13 14.15'''

class FileManagerTest(unittest.TestCase):

  def test_blank_init(self):
    fm = FileManager(None)
    self.assertEqual(fm.dir, os.path.abspath('.') + '/')

  def test_get_rooted_rooted(self):
    fm = FileManager()
    result = fm.get_rooted('/smep')
    self.assertEqual(result, '/smep')

  def test_get_rooted_relative(self):
    fm = FileManager()
    result = fm.get_rooted('glorble')
    self.assertEqual(result, fm.dir + 'glorble')

  def test_get_rooted_relative_rooted(self):
    fm = FileManager()
    result = fm.get_rooted('sources/peeno')
    self.assertEqual(result, file_manager.ROOT_DIR + 'peeno')

  def test_get_rooted_root(self):
    fm = FileManager()
    result = fm.get_rooted('/')
    self.assertEqual(result, file_manager.ROOT_DIR)

  def test_cd_root(self):
    fm = FileManager('dir/')
    fm.cd('/')
    self.assertEqual(file_manager.ROOT_DIR, fm.dir)

  def test_cd_dd(self):
    fm = FileManager(file_manager.ROOT_DIR + 'dir/subdir/')
    fm.cd('..')
    self.assertEqual(file_manager.ROOT_DIR + 'dir/', fm.dir)

  def test_cd_dd_root(self):
    fm = FileManager(file_manager.ROOT_DIR)
    fm.cd('..')
    self.assertEqual(file_manager.ROOT_DIR, fm.dir)

  def test_cd_sub(self):
    fm = FileManager('dir/')
    fm.cd('sub')
    self.assertEqual('dir/sub/', fm.dir)

  def test_cd_rooted(self):
    fm = FileManager(file_manager.ROOT_DIR)
    fm.cd('/otherdir')
    self.assertEqual(fm.dir, '/otherdir/')

  def test_remove_gutenberg(self):
    fm = FileManager(None)
    self.assertEqual(fm.remove_gutenberg(GUTENBERG_TXT), '\nalpontris\n')

  def test_remove_double_gutenberg(self):
    double_gutenberg = GUTENBERG_TXT + GUTENBERG_TXT.replace('alpontris', 'nebresion') 
    fm = FileManager(None)
    self.assertEqual(fm.remove_gutenberg(double_gutenberg), '\nalpontris\n\nnebresion\n')

  def test_get_words(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.get_words(td.tf1.name), ['a', 'b', 'c'])

  def test_get_words_relative(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.get_words(td.tf1_name), ['a', 'b', 'c'])
   
  def test_get_words_numeric(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.get_words(td.tf4.name), ['one', 'two', 'three'])

  @patch('builtins.open', mock_open(read_data=GUTENBERG_TXT))
  def test_get_words_gutenberg(self):
    fm = FileManager(None)
    self.assertEqual(fm.get_words('unused'), ['alpontris'])
   
  def test_ls(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      results = fm.ls()

      self.assertCountEqual(results, [td.tf1.name, td.d2.name])

  @patch('builtins.open', mock_open(read_data=WORD_SPLIT_TXT))
  def test_get_words_word_split(self):
    fm = FileManager(None)
    self.assertCountEqual(fm.get_words('unused'), ['one', 'two', 'three', 'four', 'five', 'sïx', 'se—ven', 'ei-ght', '9nine9', 'ten'])
   
  def test_ls(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      results = fm.ls()

      self.assertCountEqual(results, [td.tf1.name, td.d2.name])

  def test_ls_not_found(self):
    f = io.StringIO()
    with redirect_stdout(f):
      fm = FileManager('shmeeble/')
      results = fm.ls()
      self.assertIsNone(results)

  def test_ls_with_arg(self):
    with TestDirectories() as td:
      fm = FileManager(td.d4.name)
      results = fm.ls(td.d3.name)

      self.assertCountEqual(results, [td.tf3.name, td.tf4.name])

  def test_ls_with_arg_not_found(self):
    f = io.StringIO()
    with redirect_stdout(f):
      fm = FileManager('shmeeble/')
      results = fm.ls('bad_folder/')
      self.assertIsNone(results)

  def test_get_txts(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      txts = fm.get_txts()
      self.assertCountEqual(txts, td.txts)

  def test_get_txts_with_arg(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      txts = fm.get_txts(td.d3.name)
      self.assertCountEqual(txts, [td.tf3.name, td.tf4.name])

  def test_get_txts_with_bad_arg(self):
    with TestDirectories() as td:
      fm = FileManager(td.root)
      txts = fm.get_txts('worble')
      self.assertEqual(txts, [])

  @patch('random.choice')
  def test_rand_file(self, mock_choice):
    with TestDirectories() as td:
      mock_choice.side_effect = lambda a: next(filter(lambda b: '/tf2' in b, a))

      fm = FileManager(td.root)
      result = fm.rand_file()

      self.assertEqual(result, td.tf2.name)
    
  @patch('random.choice')
  def test_rand_file_with_dir(self, mock_choice):
    with TestDirectories() as td:
      mock_choice.side_effect = lambda a: sorted(a)[-1]

      fm = FileManager(td.d2.name)
      result = fm.rand_file(td.d3.name)

      self.assertEqual(result, td.tf4.name)
      
  @patch('random.choice')
  def test_rand_dir(self, mock_choice):
    with TestDirectories() as td:
      mock_choice.side_effect = [td.d2.name, td.d3.name, td.tf4.name]

      fm = FileManager(td.root)
      result = fm.rand_dir()

      self.assertEqual(fm.dir, td.root)
      self.assertEqual(result, td.tf4.name)

