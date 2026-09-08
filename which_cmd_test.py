import os
import tempfile
import unittest

from unittest.mock import MagicMock

from file_manager import FileManager
from which_cmd import SHOWN, Which
from word_index import WordIndex


class WhichTest(unittest.TestCase):

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
    which = Which(MagicMock())
    for line in ['which whale', 'WHICH whale', "which ain't", 'which well-known']:
      self.assertTrue(which.matches(line), line)
    for line in ['which', 'which two words', 'whichwhale', 'r whale']:
      self.assertFalse(which.matches(line), line)

  def test_parse_args(self):
    which = Which(MagicMock())
    self.assertEqual(which.parse_args('which whale'), ['whale'])

  ###
  ### execute
  ###

  def test_execute_not_ready(self):
    index = MagicMock()
    index.ensure_ready.return_value = False

    result = Which(index).execute(['whale'], {})

    self.assertFalse(result.ok)
    self.assertEqual(result.message, Which.not_ready_message())

  def test_execute_no_book_uses_the_word(self):
    self.add_text('shelf/one.txt', 'onlythisword')
    idx = self.make_index()

    result = Which(idx).execute(['ghostword'], {})

    self.assertTrue(result.ok)
    self.assertEqual(result.message, 'No book in the library uses "ghostword".')
    self.assertEqual(result.data, {'word': 'ghostword', 'count': 0, 'texts': []})

  def test_execute_lists_the_books_using_a_word(self):
    self.add_text('shelf/one.txt', 'harpooneer')
    idx = self.make_index()

    result = Which(idx).execute(['harpooneer'], {})

    self.assertTrue(result.ok)
    self.assertEqual(result.message,
                     '"harpooneer" is in 1 of 1 books: shelf/one.txt')
    self.assertEqual(result.data,
                     {'word': 'harpooneer', 'count': 1, 'texts': ['shelf/one.txt']})

  def test_execute_lowercases_the_word_argument(self):
    self.add_text('shelf/one.txt', 'harpooneer')
    idx = self.make_index()

    result = Which(idx).execute(['HARPOONEER'], {})

    self.assertEqual(result.data['word'], 'harpooneer')
    self.assertEqual(result.data['count'], 1)

  def test_execute_truncates_the_message_past_shown_but_keeps_all_texts_in_data(self):
    total = SHOWN + 3
    for i in range(total):
      self.add_text(f'shelf/book{i:02d}.txt', 'common')
    idx = self.make_index()

    result = Which(idx).execute(['common'], {})

    self.assertTrue(result.ok)
    self.assertEqual(result.data['count'], total)
    self.assertEqual(len(result.data['texts']), total)
    self.assertIn(f'and {total - SHOWN} more', result.message)
    # Only the first SHOWN texts are named in the message.
    shown_texts = sorted(f'shelf/book{i:02d}.txt' for i in range(total))[:SHOWN]
    for path in shown_texts:
      self.assertIn(path, result.message)


if __name__ == '__main__':
  unittest.main()
