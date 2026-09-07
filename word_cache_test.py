import os
import time
import unittest

from fake_directories import FakeDirectories
from file_manager import InvalidPath, UnreadableSource
from word_cache import CachingFileManager


class WordCacheTest(unittest.TestCase):

  def test_second_read_is_a_hit(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)

      first = fm.get_words(td.tf1_path)
      second = fm.get_words(td.tf1_path)

      self.assertEqual(first, second)
      self.assertEqual(fm.stats()['hits'], 1)
      self.assertEqual(fm.stats()['misses'], 1)

  def test_edited_file_is_reparsed(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)
      self.assertCountEqual(fm.get_words(td.tf1_path), ['a', 'b', 'c'])

      # Same path, new contents: the modification time is the key.
      time.sleep(0.01)
      td.write_file(td.tf1, 'zebra\n')
      os.utime(td.tf1.name, (time.time() + 1, time.time() + 1))

      self.assertCountEqual(fm.get_words(td.tf1_path), ['zebra'])

  def test_missing_file_still_raises_the_real_error(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)
      with self.assertRaises(UnreadableSource):
        fm.get_words('nope.txt')

  def test_escape_still_raises(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)
      with self.assertRaises(InvalidPath):
        fm.get_words('../../etc/passwd')

  def test_cached_size_never_parses(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)

      self.assertIsNone(fm.cached_size(td.tf1_path))
      self.assertEqual(fm.stats()['misses'], 0)

      fm.get_words(td.tf1_path)
      self.assertEqual(fm.cached_size(td.tf1_path), 3)

  def test_eviction_is_bounded_by_words(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root, max_words=5)

      fm.get_words(td.tf1_path)   # 3 words
      fm.get_words(td.tf4_path)   # 3 words, tips it over the budget

      self.assertLessEqual(fm.stats()['words'], 5)
      # The oldest went; the newest stayed.
      self.assertIsNone(fm.cached_size(td.tf1_path))
      self.assertIsNotNone(fm.cached_size(td.tf4_path))

  def test_a_pool_larger_than_the_budget_is_still_usable(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root, max_words=1)
      self.assertCountEqual(fm.get_words(td.tf1_path), ['a', 'b', 'c'])
      self.assertEqual(fm.cached_size(td.tf1_path), 3)

  def test_warm_reads_what_it_can_and_ignores_the_rest(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)

      done = fm.warm([td.tf1_path, 'nope.txt', '../escape', td.tf4_path])

      self.assertEqual(done, 2)
      self.assertEqual(fm.stats()['files'], 2)

  def test_warm_in_background_finishes(self):
    with FakeDirectories() as td:
      fm = CachingFileManager(td.root)
      thread = fm.warm_in_background(fm.get_txts())
      thread.join(timeout=10)
      self.assertFalse(thread.is_alive())
      self.assertEqual(fm.stats()['files'], 5)
