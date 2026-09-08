import os
import tempfile
import unittest

from unittest.mock import patch

from fake_file_manager import FakeFileManager
from word_index import CACHE_FILE, FORMAT_VERSION, NEIGHBOUR_LIMIT, WordIndex


class WordIndexTest(unittest.TestCase):

  # Writes an extra text into a FakeFileManager's tree, the way
  # rand_diff_cmd_test.py's make_dict adds a dicts/ folder to one.
  def add_text(self, tfm, rel_path, content):
    full = os.path.join(tfm.td.root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w') as f:
      f.write(content)
    return full

  ###
  ### building
  ###

  def test_build_counts_a_word_in_one_text(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'lonewolf.txt', 'solivagant other')
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      self.assertEqual(idx.doc_count('solivagant'), 1)
      self.assertEqual(idx.texts_for('solivagant'), ['lonewolf.txt'])

  def test_build_counts_a_word_in_several_texts(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'shelf/one.txt', 'sharedword onlyone')
      self.add_text(tfm, 'shelf/two.txt', 'sharedword onlytwo')
      self.add_text(tfm, 'shelf/three.txt', 'sharedword onlythree')
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      self.assertEqual(idx.doc_count('sharedword'), 3)
      self.assertCountEqual(
          idx.texts_for('sharedword'),
          ['shelf/one.txt', 'shelf/two.txt', 'shelf/three.txt'])
      self.assertEqual(idx.doc_count('onlyone'), 1)

  def test_doc_count_and_texts_for_a_word_the_library_never_uses(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      self.assertEqual(idx.doc_count('nosuchword'), 0)
      self.assertEqual(idx.texts_for('nosuchword'), [])

  def test_queries_are_case_insensitive_though_the_index_stores_lower_case(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'casing.txt', 'lowercaseword')
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      self.assertEqual(idx.doc_count('LOWERCASEWORD'), 1)
      self.assertEqual(idx.doc_count('LowerCaseWord'), 1)
      self.assertEqual(idx.texts_for('LOWERCASEWORD'), ['casing.txt'])

  ###
  ### books() / NOT_BOOKS
  ###
  ###
  # The single most important behaviour of this module: dicts/ and custom/
  # hold word lists, not books, and counting them wrecks what the index is
  # for (see the NOT_BOOKS comment in word_index.py).
  ###

  def test_books_excludes_dicts_and_custom_folders(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'shelf/book.txt', 'onlyinbook harpooneerlike')
      self.add_text(tfm, 'dicts/freq.txt', 'harpooneerlike dictonlyword')
      self.add_text(tfm, 'custom/pool.txt', 'customonlyword')
      idx = WordIndex(tfm, cache_dir=cache)

      books = idx.books()
      self.assertIn('shelf/book.txt', books)
      self.assertNotIn('dicts/freq.txt', books)
      self.assertNotIn('custom/pool.txt', books)

  def test_a_word_only_in_a_dictionary_has_a_doc_count_of_zero(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'shelf/book.txt', 'onlyinbook')
      self.add_text(tfm, 'dicts/freq.txt', 'dictonlyword')
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      self.assertEqual(idx.doc_count('dictonlyword'), 0)

  def test_a_word_only_in_a_custom_list_has_a_doc_count_of_zero(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'shelf/book.txt', 'onlyinbook')
      self.add_text(tfm, 'custom/pool.txt', 'customonlyword')
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      self.assertEqual(idx.doc_count('customonlyword'), 0)

  def test_a_word_in_one_book_and_one_dictionary_has_a_doc_count_of_one(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'shelf/book.txt', 'harpooneerlike')
      self.add_text(tfm, 'dicts/freq.txt', 'harpooneerlike')
      idx = WordIndex(tfm, cache_dir=cache)

      idx.build()

      # Without NOT_BOOKS this would look like two texts share the word,
      # which is exactly the miscount the exclusion exists to prevent.
      self.assertEqual(idx.doc_count('harpooneerlike'), 1)
      self.assertEqual(idx.texts_for('harpooneerlike'), ['shelf/book.txt'])

  ###
  ### filter_rare
  ###

  def test_filter_rare_keeps_words_at_or_under_the_threshold(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'freq/one.txt', 'once twice thrice')
      self.add_text(tfm, 'freq/two.txt', 'twice thrice')
      self.add_text(tfm, 'freq/three.txt', 'thrice')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      self.assertEqual(idx.filter_rare(['once', 'twice', 'thrice'], max_texts=1),
                       ['once'])
      self.assertCountEqual(
          idx.filter_rare(['once', 'twice', 'thrice'], max_texts=2),
          ['once', 'twice'])

  def test_filter_rare_drops_commoner_words(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'freq/one.txt', 'common')
      self.add_text(tfm, 'freq/two.txt', 'common')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      self.assertEqual(idx.filter_rare(['common'], max_texts=1), [])

  def test_filter_rare_drops_a_word_the_index_has_never_seen(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'freq/one.txt', 'real')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      # A count of zero is not evidence of rarity; it is evidence the word
      # came from outside the library, so even a generous threshold must
      # not let it through.
      self.assertEqual(idx.filter_rare(['ghostword'], max_texts=1000), [])
      self.assertEqual(idx.filter_rare(['real', 'ghostword'], max_texts=1),
                       ['real'])

  ###
  ### neighbours
  ###

  def test_neighbours_ranks_shared_books_higher_and_excludes_no_overlap(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'nb/a.txt', 'mine tie1 tie2 tie3 partial')
      self.add_text(tfm, 'nb/b.txt', 'mine tie1 tie2 tie3')
      self.add_text(tfm, 'nb/c.txt', 'unrelated')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      # Ties are broken by random.shuffle before a stable sort by score, so
      # this patches shuffle into a deterministic pre-sort rather than
      # asserting an order that is random by design (the module's own
      # comment on neighbours() explains why an alphabetical tiebreak alone
      # would be a bad idea, but with the tier pinned first the result is
      # deterministic).
      def deterministic_shuffle(seq):
        seq.sort(key=lambda pair: pair[0])

      with patch('random.shuffle', side_effect=deterministic_shuffle):
        scored = idx.neighbours('mine', limit=10)

      words = [w for w, _ in scored]
      scores = dict(scored)
      # tie1/tie2/tie3 share exactly mine's two texts (Jaccard 1.0); partial
      # shares only one of the two (Jaccard 0.5); unrelated shares none, so
      # it is never even a candidate.
      self.assertEqual(words, ['tie1', 'tie2', 'tie3', 'partial'])
      self.assertAlmostEqual(scores['tie1'], 1.0)
      self.assertAlmostEqual(scores['partial'], 0.5)
      self.assertNotIn('unrelated', words)

  def test_neighbours_for_a_word_absent_from_the_index_is_empty(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'nb/a.txt', 'something')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      self.assertEqual(idx.neighbours('neverindexed'), [])

  ###
  ### too_common
  ###

  def test_too_common_around_the_neighbour_limit_boundary(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      # NEIGHBOUR_LIMIT texts share 'atlimit'; one more shares 'overlimit'.
      for i in range(NEIGHBOUR_LIMIT + 1):
        content = 'overlimit'
        if i < NEIGHBOUR_LIMIT:
          content += ' atlimit'
        self.add_text(tfm, f'bulk/book{i}.txt', content)
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      self.assertEqual(idx.doc_count('atlimit'), NEIGHBOUR_LIMIT)
      self.assertFalse(idx.too_common('atlimit'))

      self.assertEqual(idx.doc_count('overlimit'), NEIGHBOUR_LIMIT + 1)
      self.assertTrue(idx.too_common('overlimit'))

  ###
  ### persistence
  ###

  def test_save_then_load_into_a_fresh_index_reproduces_the_same_answers(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      self.add_text(tfm, 'persist/two.txt', 'beta gamma')
      idx1 = WordIndex(tfm, cache_dir=cache)
      idx1.build()
      self.assertTrue(idx1.save())

      idx2 = WordIndex(tfm, cache_dir=cache)
      self.assertTrue(idx2.load())

      for word in ('alpha', 'beta', 'gamma', 'neverindexed'):
        with self.subTest(word=word):
          self.assertEqual(idx2.doc_count(word), idx1.doc_count(word))
          self.assertEqual(idx2.texts_for(word), idx1.texts_for(word))
      self.assertEqual(idx2.stats(), idx1.stats())

  def test_load_false_and_state_preserved_when_file_is_absent(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()  # ready, but never saved: cache is empty.
      self.assertTrue(idx.ready)

      self.assertFalse(idx.load())

      self.assertTrue(idx.ready)
      self.assertEqual(idx.doc_count('alpha'), 1)

  def test_load_false_and_state_preserved_when_header_is_not_the_magic_bytes(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()
      self.assertTrue(idx.save())

      path = os.path.join(cache, CACHE_FILE)
      with open(path, 'wb') as f:
        f.write(b'NOTANINDEX\nsome bytes that are not the real format at all')

      self.assertFalse(idx.load())

      self.assertTrue(idx.ready)
      self.assertEqual(idx.doc_count('beta'), 1)

  def test_load_false_and_state_preserved_when_format_version_differs(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()

      with patch('word_index.FORMAT_VERSION', FORMAT_VERSION + 1):
        self.assertTrue(idx.save())

      # Saved under a version that no longer matches the module's; loading
      # it back under the real version must be refused, not misread.
      self.assertFalse(idx.load())

      self.assertTrue(idx.ready)
      self.assertEqual(idx.doc_count('alpha'), 1)

  def test_load_false_and_state_preserved_when_file_is_truncated(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()
      self.assertTrue(idx.save())

      path = os.path.join(cache, CACHE_FILE)
      with open(path, 'rb') as f:
        data = f.read()
      with open(path, 'wb') as f:
        f.write(data[:-10])  # chop off the tail, mid-blob.

      self.assertFalse(idx.load())

      self.assertTrue(idx.ready)
      self.assertEqual(idx.doc_count('beta'), 1)

  def test_load_false_after_a_text_is_modified(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      full = self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()
      self.assertTrue(idx.save())

      # Same content, different mtime: _still_current compares mtimes, not
      # content, so this alone must invalidate the saved index.
      old = os.path.getmtime(full)
      os.utime(full, (old + 100, old + 100))

      fresh = WordIndex(tfm, cache_dir=cache)
      self.assertFalse(fresh.load())

  def test_load_false_after_a_text_is_added(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()
      self.assertTrue(idx.save())

      self.add_text(tfm, 'persist/two.txt', 'gamma')

      fresh = WordIndex(tfm, cache_dir=cache)
      self.assertFalse(fresh.load())

  def test_load_false_after_a_text_is_removed(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'persist/one.txt', 'alpha beta')
      doomed = self.add_text(tfm, 'persist/two.txt', 'gamma')
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()
      self.assertTrue(idx.save())

      os.remove(doomed)

      fresh = WordIndex(tfm, cache_dir=cache)
      self.assertFalse(fresh.load())

  ###
  ### ensure_ready
  ###

  def test_ensure_ready_builds_when_nothing_is_cached(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      self.add_text(tfm, 'er/one.txt', 'alpha')
      idx = WordIndex(tfm, cache_dir=cache)
      self.assertFalse(idx.ready)

      self.assertTrue(idx.ensure_ready())

      self.assertTrue(idx.ready)
      self.assertEqual(idx.doc_count('alpha'), 1)

  def test_ensure_ready_is_a_noop_when_already_ready(self):
    with (FakeFileManager() as tfm, tempfile.TemporaryDirectory() as cache):
      idx = WordIndex(tfm, cache_dir=cache)
      idx.build()
      self.assertTrue(idx.ready)

      with patch.object(idx, 'load_or_build') as mock_lob:
        self.assertTrue(idx.ensure_ready())
        mock_lob.assert_not_called()


if __name__ == '__main__':
  unittest.main()
