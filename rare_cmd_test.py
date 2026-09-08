import os
import tempfile
import unittest

from unittest.mock import MagicMock

from file_manager import FileManager
from rare_cmd import Rare
from word_index import WordIndex


class RareTest(unittest.TestCase):

  def setUp(self):
    self.lib = tempfile.TemporaryDirectory()
    self.cache = tempfile.TemporaryDirectory()
    self.addCleanup(self.lib.cleanup)
    self.addCleanup(self.cache.cleanup)
    self.fm = FileManager(self.lib.name)

  def add_text(self, rel_path, content):
    full = os.path.join(self.lib.name, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w') as f:
      f.write(content)
    return full

  def make_index(self):
    return WordIndex(self.fm, cache_dir=self.cache.name)

  ###
  ### matches / parse_args
  ###

  def test_matches(self):
    rare = Rare(MagicMock())
    for line in ['rare', 'rare 3', 'RARE 10']:
      self.assertTrue(rare.matches(line), line)
    for line in ['r', 'rare abc', 'rared', 'rare3', 'rare -1']:
      self.assertFalse(rare.matches(line), line)

  def test_parse_args(self):
    rare = Rare(MagicMock())
    self.assertEqual(rare.parse_args('rare'), [])
    self.assertEqual(rare.parse_args('rare 3'), ['3'])

  ###
  ### execute: failure branches that never need a real index
  ###

  def test_execute_fails_with_an_empty_active_pool(self):
    for context in ({}, {'words': []}):
      with self.subTest(context=context):
        result = Rare(MagicMock()).execute([], context)
        self.assertFalse(result.ok)
        self.assertIn('No words are loaded', result.message)
        self.assertFalse(result.updates)

  def test_execute_rare_0_fails_before_touching_the_index(self):
    index = MagicMock()
    result = Rare(index).execute(['0'], {'words': ['a']})

    self.assertFalse(result.ok)
    self.assertIn('Ask for words in at least one book', result.message)
    self.assertFalse(result.updates)
    index.ensure_ready.assert_not_called()

  def test_execute_negative_n_fails(self):
    result = Rare(MagicMock()).execute(['-1'], {'words': ['a']})
    self.assertFalse(result.ok)
    self.assertIn('Ask for words in at least one book', result.message)

  def test_execute_not_ready(self):
    index = MagicMock()
    index.ensure_ready.return_value = False

    result = Rare(index).execute([], {'words': ['a']})

    self.assertFalse(result.ok)
    self.assertEqual(result.message, Rare.not_ready_message())

  ###
  ### execute: the real filtering behaviour
  ###

  def test_execute_default_keeps_words_in_at_most_one_book(self):
    self.add_text('a.txt', 'rare1 common')
    self.add_text('b.txt', 'common')
    self.add_text('c.txt', 'common')
    idx = self.make_index()

    result = Rare(idx).execute([], {'words': ['rare1', 'common', 'neverindexed']})

    self.assertTrue(result.ok)
    self.assertEqual(result.message, '1 of 3 words are in one book.')
    self.assertEqual(result.updates, {'words': ['rare1']})
    self.assertEqual(result.data, {'size': 1, 'from': 3, 'max_texts': 1})

  def test_execute_with_n_keeps_words_in_at_most_n_books(self):
    self.add_text('a.txt', 'rare1 common')
    self.add_text('b.txt', 'common')
    self.add_text('c.txt', 'common')
    idx = self.make_index()

    result = Rare(idx).execute(['3'], {'words': ['rare1', 'common', 'neverindexed']})

    self.assertTrue(result.ok)
    self.assertEqual(result.message, '2 of 3 words are in at most 3 books.')
    self.assertEqual(result.updates, {'words': ['rare1', 'common']})
    self.assertEqual(result.data, {'size': 2, 'from': 3, 'max_texts': 3})

  def test_execute_fails_and_leaves_the_pool_alone_when_nothing_qualifies(self):
    self.add_text('a.txt', 'common')
    self.add_text('b.txt', 'common')
    idx = self.make_index()

    result = Rare(idx).execute([], {'words': ['common']})

    self.assertFalse(result.ok)
    self.assertIn('None of those 1 words are in 1 book(s) or fewer', result.message)
    self.assertIn('keeping the current pool', result.message)
    # A refusal must not store an empty pool: no updates at all.
    self.assertFalse(result.updates)

  def test_execute_drops_words_the_index_has_never_seen(self):
    self.add_text('a.txt', 'real')
    idx = self.make_index()

    result = Rare(idx).execute(['1000'], {'words': ['real', 'ghostword']})

    self.assertTrue(result.ok)
    self.assertEqual(result.updates, {'words': ['real']})


if __name__ == '__main__':
  unittest.main()
