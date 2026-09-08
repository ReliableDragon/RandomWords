import logging
import os
import unittest

from unittest.mock import patch, mock_open

import file_manager
from file_manager import FileManager, InvalidPath, UnreadableSource
from fake_directories import FakeDirectories

logger = logging.getLogger(__name__)

GUTENBERG_TXT = '''A header.
*** START OF THE PROJECT GUTENBERG EBOOK KWANGLAP ***
alpontris
*** END OF THE PROJECT GUTENBERG EBOOK KWANGLAP ***
A footer.'''
UNCLOSED_GUTENBERG_TXT = '''A header.
*** START OF THE PROJECT GUTENBERG EBOOK KWANGLAP ***
alpontris'''
WORD_SPLIT_TXT = '''one--two
three four*five sïx se—ven ei-ght 9nine9 ten 11 12-13 14.15'''
APOSTROPHE_TXT = "The cat ain't Ahab’s; THE CAT is a cat."


class FileManagerTest(unittest.TestCase):

  ###
  ### resolve: the only place a path can enter the library
  ###

  def test_resolve_root(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertEqual(fm.resolve(''), fm.root)

  def test_resolve_nested(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertEqual(fm.resolve(td.tf1_path), os.path.realpath(td.tf1.name))

  def test_resolve_rejects_absolute(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      with self.assertRaises(InvalidPath):
        fm.resolve('/etc/passwd')

  def test_resolve_rejects_parent_segment(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      for path in ['..', '../..', 'a/../../b', '../etc/passwd']:
        with self.subTest(path=path):
          with self.assertRaises(InvalidPath):
            fm.resolve(path)

  def test_resolve_rejects_symlink_out_of_the_tree(self):
    with FakeDirectories() as td:
      outside = os.path.dirname(os.path.realpath(td.root))
      link = os.path.join(td.root, 'escape')
      os.symlink(outside, link)

      fm = FileManager(td.root)
      # The string checks pass; only the realpath check catches this one.
      with self.assertRaises(InvalidPath):
        fm.resolve('escape/anything')

  def test_resolve_allows_a_legitimately_deep_path(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      deep = td.tf3_path
      self.assertEqual(fm.resolve(deep), os.path.realpath(td.tf3.name))

  def test_resolve_tolerates_redundant_segments(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertEqual(fm.resolve('./' + td.tf1_path), os.path.realpath(td.tf1.name))

  def test_relative_round_trips(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertEqual(fm.relative(fm.resolve(td.tf1_path)), td.tf1_path)
      self.assertEqual(fm.relative(fm.resolve('')), '')

  def test_is_dir(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertTrue(fm.is_dir(td.d2_path))
      self.assertFalse(fm.is_dir(td.tf1_path))
      self.assertFalse(fm.is_dir('/etc'))

  ###
  ### get_words
  ###

  def test_get_words(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.get_words(td.tf1_path), ['a', 'b', 'c'])

  def test_get_words_numeric(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.get_words(td.tf4_path), ['one', 'two', 'three'])

  def test_get_words_missing_file_raises(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      with self.assertRaises(UnreadableSource) as caught:
        fm.get_words('no_such_file.txt')
      self.assertEqual(str(caught.exception), 'Invalid filename: no_such_file.txt')

  def test_get_words_outside_the_library_raises(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      with self.assertRaises(InvalidPath):
        fm.get_words('/etc/hosts')

  @patch('builtins.open', mock_open(read_data=GUTENBERG_TXT))
  def test_get_words_gutenberg(self):
    self.assertEqual(FileManager().get_words('unused'), ['alpontris'])

  @patch('builtins.open', mock_open(read_data=UNCLOSED_GUTENBERG_TXT))
  def test_get_words_gutenberg_without_footer(self):
    self.assertCountEqual(FileManager().get_words('unused'), ['alpontris'])

  @patch('builtins.open', mock_open(read_data=WORD_SPLIT_TXT))
  def test_get_words_word_split(self):
    self.assertCountEqual(
        FileManager().get_words('unused'),
        ['one', 'two', 'three', 'four', 'five', 'sïx', 'se', 'ven', 'ei-ght',
         '9nine9', 'ten'])

  @patch('builtins.open', mock_open(read_data=APOSTROPHE_TXT))
  def test_get_words_case_and_apostrophes(self):
    # 'The'/'THE' collapse to one word, and possessives stay whole.
    self.assertCountEqual(FileManager().get_words('unused'),
                          ['the', 'cat', "ain't", 'ahab’s', 'is', 'a'])

  def test_remove_gutenberg(self):
    self.assertEqual(FileManager().remove_gutenberg(GUTENBERG_TXT), '\nalpontris\n')

  def test_remove_double_gutenberg(self):
    doubled = GUTENBERG_TXT + GUTENBERG_TXT.replace('alpontris', 'nebresion')
    self.assertEqual(FileManager().remove_gutenberg(doubled),
                     '\nalpontris\n\nnebresion\n')

  ###
  ### listing
  ###

  def test_ls_root(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.ls(), [td.tf1_path, td.d2_path])

  def test_ls_subfolder(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.ls(td.d3_path), [td.tf3_path, td.tf4_path])

  def test_ls_skips_hidden_dirs(self):
    with FakeDirectories() as td:
      os.mkdir(os.path.join(td.root, '.hidden'))
      fm = FileManager(td.root)
      self.assertCountEqual(fm.ls(), [td.tf1_path, td.d2_path])

  def test_ls_missing_folder(self):
    with FakeDirectories() as td:
      self.assertIsNone(FileManager(td.root).ls('nope'))

  def test_ls_a_file_is_not_a_folder(self):
    with FakeDirectories() as td:
      self.assertIsNone(FileManager(td.root).ls(td.tf1_path))

  def test_get_txts(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(
          fm.get_txts(),
          [td.tf1_path, td.tf2_path, td.tf3_path, td.tf4_path, td.tf5_path])

  def test_get_txts_subfolder(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertCountEqual(fm.get_txts(td.d3_path), [td.tf3_path, td.tf4_path])

  def test_get_txts_missing_folder(self):
    with FakeDirectories() as td:
      self.assertEqual(FileManager(td.root).get_txts('worble'), [])

  ###
  ### random selection
  ###

  @patch('random.choice')
  def test_rand_file(self, mock_choice):
    with FakeDirectories() as td:
      mock_choice.side_effect = lambda seq: next(p for p in seq if 'tf2' in p)
      self.assertEqual(FileManager(td.root).rand_file(), td.tf2_path)

  @patch('random.choice')
  def test_rand_file_in_a_subfolder(self, mock_choice):
    with FakeDirectories() as td:
      mock_choice.side_effect = lambda seq: sorted(seq)[-1]
      result = FileManager(td.root).rand_file(td.d3_path)
      self.assertIn(result, [td.tf3_path, td.tf4_path])

  def test_rand_file_empty_folder(self):
    with FakeDirectories() as td:
      os.mkdir(os.path.join(td.root, 'empty'))
      self.assertIsNone(FileManager(td.root).rand_file('empty'))

  @patch('random.choice')
  def test_rand_dir(self, mock_choice):
    with FakeDirectories() as td:
      mock_choice.side_effect = [td.d2_path, td.d3_path, td.tf4_path]
      self.assertEqual(FileManager(td.root).rand_dir(), td.tf4_path)

  @patch('random.choice')
  def test_rand_dir_skips_empty_folders(self, mock_choice):
    with FakeDirectories() as td:
      empty = os.path.join(td.d2.name, 'empty_folder')
      os.mkdir(empty)
      # This manager is rooted at d2, so paths are relative to d2, not to
      # the fixture root.
      fm = FileManager(td.d2.name)
      # Choose the empty folder first; it must fall back to a real file.
      mock_choice.side_effect = [fm.relative(empty), fm.relative(td.tf2.name)]

      self.assertEqual(fm.rand_dir(), fm.relative(td.tf2.name))

  def test_root_defaults_to_the_sources_directory(self):
    self.assertEqual(FileManager().root, os.path.realpath(file_manager.ROOT_DIR))

  ###
  ### write_path: the one place a pool name becomes a filename
  ###

  def test_write_path_accepts_ordinary_names(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      for name in ['rare', 'pool_2', 'A1']:
        with self.subTest(name=name):
          self.assertEqual(fm.write_path(name),
                           os.path.join(fm.root, 'custom', f'{name}.txt'))

  def test_write_path_rejects_anything_that_is_not_a_bare_name(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      for name in ['a/b', '../x', '/abs', 'a.txt', '']:
        with self.subTest(name=name):
          with self.assertRaises(InvalidPath):
            fm.write_path(name)

  ###
  ### pool_exists
  ###

  def test_pool_exists_before_and_after_a_write(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertFalse(fm.pool_exists('rare'))
      fm.write_pool('rare', ['a'])
      self.assertTrue(fm.pool_exists('rare'))

  def test_pool_exists_rejects_a_bad_name(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      with self.assertRaises(InvalidPath):
        fm.pool_exists('a/b')

  ###
  ### write_pool
  ###

  def test_write_pool_writes_one_word_per_line_with_a_trailing_newline(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      rel = fm.write_pool('rare', ['ambergris', 'leviathan', 'mizzen'])
      self.assertEqual(rel, 'custom/rare.txt')
      with open(fm.resolve(rel), encoding='utf-8') as f:
        content = f.read()
      self.assertEqual(content, 'ambergris\nleviathan\nmizzen\n')

  def test_write_pool_creates_the_custom_folder(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      self.assertFalse(os.path.isdir(os.path.join(td.root, 'custom')))
      fm.write_pool('rare', ['a'])
      self.assertTrue(os.path.isdir(os.path.join(td.root, 'custom')))

  def test_write_pool_leaves_no_temporary_file_behind(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      rel = fm.write_pool('rare', ['a', 'b'])
      folder = os.path.dirname(fm.resolve(rel))
      self.assertEqual(os.listdir(folder), [os.path.basename(fm.resolve(rel))])

  def test_write_pool_replaces_the_previous_contents(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      fm.write_pool('rare', ['old', 'words'])
      fm.write_pool('rare', ['new'])
      self.assertCountEqual(fm.get_words('custom/rare.txt'), ['new'])

  def test_write_pool_reads_back_through_get_words_as_the_same_words(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      words = ['ambergris', 'civet', 'copal']
      rel = fm.write_pool('rare', words)
      self.assertCountEqual(fm.get_words(rel), words)

  def test_write_pool_rejects_a_bad_name_before_writing_anything(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      with self.assertRaises(InvalidPath):
        fm.write_pool('a/b', ['a'])
      self.assertFalse(os.path.exists(os.path.join(td.root, 'custom')))

  @patch('tempfile.mkstemp')
  def test_write_pool_raises_unreadable_source_when_the_write_fails(self, mock_mkstemp):
    mock_mkstemp.side_effect = OSError('disk full')
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      with self.assertRaises(UnreadableSource):
        fm.write_pool('rare', ['a'])
