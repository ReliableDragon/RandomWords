import os
import tempfile
import unittest

from unittest.mock import MagicMock

from file_manager import FileManager
from like_cmd import MAX_COUNT, Like
from word_index import NEIGHBOUR_LIMIT, WordIndex


class LikeTest(unittest.TestCase):

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
    like = Like(MagicMock())
    for line in ['like whale', 'like whale 5', 'LIKE whale', "like ain't"]:
      self.assertTrue(like.matches(line), line)
    for line in ['like', 'like whale five', 'like whale 5 6', 'likewhale']:
      self.assertFalse(like.matches(line), line)

  def test_parse_args(self):
    like = Like(MagicMock())
    self.assertEqual(like.parse_args('like whale'), ['whale'])
    self.assertEqual(like.parse_args('like whale 5'), ['whale', '5'])

  ###
  ### execute: failure branches
  ###

  def test_execute_not_ready(self):
    index = MagicMock()
    index.ensure_ready.return_value = False

    result = Like(index).execute(['whale'], {})

    self.assertFalse(result.ok)
    self.assertEqual(result.message, Like.not_ready_message())

  def test_execute_count_less_than_one_fails(self):
    index = MagicMock()
    index.ensure_ready.return_value = True

    result = Like(index).execute(['whale', '0'], {})

    self.assertFalse(result.ok)
    self.assertIn('Ask for at least one word', result.message)

  def test_execute_unknown_word_fails(self):
    self.add_text('a.txt', 'something')
    idx = self.make_index()

    result = Like(idx).execute(['ghostword'], {})

    self.assertFalse(result.ok)
    self.assertEqual(result.message, 'No book in the library uses "ghostword".')

  def test_execute_too_common_word_fails(self):
    for i in range(NEIGHBOUR_LIMIT + 1):
      self.add_text(f'bulk/book{i}.txt', 'overlimit')
    idx = self.make_index()

    result = Like(idx).execute(['overlimit'], {})

    self.assertFalse(result.ok)
    self.assertIn(f'"overlimit" is in {NEIGHBOUR_LIMIT + 1} books', result.message)
    self.assertIn('too many to be distinctive', result.message)

  def test_execute_nothing_keeps_company_fails(self):
    self.add_text('a.txt', 'onlyword')
    idx = self.make_index()

    result = Like(idx).execute(['onlyword'], {})

    self.assertFalse(result.ok)
    self.assertEqual(result.message, 'Nothing else keeps company with "onlyword".')

  ###
  ### execute: the count clamp
  ###

  def test_execute_count_is_clamped_to_max_count(self):
    index = MagicMock()
    index.ensure_ready.return_value = True
    index.doc_count.return_value = 1
    index.too_common.return_value = False
    index.neighbours.return_value = [('friend', 1.0)]

    result = Like(index).execute(['whale', str(MAX_COUNT + 500)], {})

    self.assertTrue(result.ok)
    index.neighbours.assert_called_once_with('whale', MAX_COUNT)

  ###
  ### execute: success
  ###

  def test_execute_returns_ranked_words_with_scores(self):
    self.add_text('a.txt', 'target friend')
    self.add_text('b.txt', 'target friend other')
    idx = self.make_index()

    result = Like(idx).execute(['target'], {})

    self.assertTrue(result.ok)
    self.assertEqual(result.message, 'friend other')
    self.assertEqual(result.data,
                     {'word': 'target', 'drawn': ['friend', 'other'],
                      'scores': [1.0, 0.5]})

  def test_execute_lowercases_the_word_argument(self):
    self.add_text('a.txt', 'target friend')
    self.add_text('b.txt', 'target friend')
    idx = self.make_index()

    result = Like(idx).execute(['TARGET'], {})

    self.assertTrue(result.ok)
    self.assertEqual(result.data['word'], 'target')


if __name__ == '__main__':
  unittest.main()
