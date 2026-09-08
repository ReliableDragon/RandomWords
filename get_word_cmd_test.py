import unittest

from unittest.mock import patch

from get_word_cmd import GetWord

class GetWordTest(unittest.TestCase):

  @patch('random.sample')
  def test_execute(self, mock_sample):
    mock_sample.side_effect = lambda population, k: population[:k]

    getword = GetWord()

    result = getword.execute([], {'words': ['a', 'b', 'c']})

    self.assertEqual(result.message, 'a')
    self.assertEqual(result.data, {'drawn': ['a']})

  @patch('random.sample')
  def test_execute_multi(self, mock_sample):
    mock_sample.side_effect = lambda population, k: population[:k]

    getword = GetWord()

    result = getword.execute([3], {'words': ['a', 'b', 'c']})

    self.assertEqual(result.message, 'a b c')
    self.assertEqual(result.data, {'drawn': ['a', 'b', 'c']})

  def test_execute_without_words(self):
    result = GetWord().execute([], {})
    self.assertFalse(result.ok)
    self.assertIn('No words are loaded', result.message)

  def test_execute_with_empty_pool(self):
    result = GetWord().execute([], {'words': []})
    self.assertFalse(result.ok)
    self.assertIn('No words are loaded', result.message)

  # A draw the size of the whole pool is a full, order-shuffled sample: every
  # word comes back, and none of them twice. This exercises the real
  # random.sample rather than a patched one, since "every word exactly once"
  # is true regardless of which order it picks.
  def test_execute_draw_of_pool_size_returns_every_word_once(self):
    result = GetWord().execute([3], {'words': ['a', 'b', 'c']})

    self.assertEqual(sorted(result.data['drawn']), ['a', 'b', 'c'])
    self.assertEqual(len(result.data['drawn']), 3)

  # Asking for more words than the pool holds can't be satisfied without
  # repeats, so the count wins over distinctness: the caller still gets
  # exactly what they asked for.
  def test_execute_draw_larger_than_pool_returns_requested_count(self):
    result = GetWord().execute([1000], {'words': ['a', 'b', 'c']})

    self.assertEqual(len(result.data['drawn']), 1000)
    for word in result.data['drawn']:
      self.assertIn(word, ['a', 'b', 'c'])

  def test_execute_draw_of_one(self):
    result = GetWord().execute([1], {'words': ['a', 'b', 'c']})

    self.assertEqual(len(result.data['drawn']), 1)
    self.assertIn(result.data['drawn'][0], ['a', 'b', 'c'])
