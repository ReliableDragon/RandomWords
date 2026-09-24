import unittest
from sampling import sample_distinct_weighted, sample_words


class SamplingTest(unittest.TestCase):

  def test_empty_population(self):
    self.assertEqual(sample_distinct_weighted([], [], 5), [])
    self.assertEqual(sample_words([], {}, 5), [])
    self.assertEqual(sample_words(['a', 'b'], {}, 0), [])

  def test_single_item(self):
    items = ['apple']
    weights = [10]
    self.assertEqual(sample_distinct_weighted(items, weights, 1), ['apple'])

  def test_distinct_sample_never_repeats_when_k_le_len(self):
    items = ['a', 'b', 'c', 'd', 'e']
    weights = [1, 2, 5, 10, 20]
    for _ in range(50):
      drawn = sample_distinct_weighted(items, weights, 4)
      self.assertEqual(len(drawn), 4)
      self.assertEqual(len(set(drawn)), 4)

  def test_k_greater_than_len_falls_back_to_replacement(self):
    items = ['a', 'b']
    weights = [1, 1]
    drawn = sample_distinct_weighted(items, weights, 10)
    self.assertEqual(len(drawn), 10)
    for item in drawn:
      self.assertIn(item, items)

  def test_skewed_weights_distribution(self):
    items = ['rare', 'common']
    weights = [1, 99]
    common_count = 0
    draws = 500
    for _ in range(draws):
      res = sample_distinct_weighted(items, weights, 1)
      if res[0] == 'common':
        common_count += 1
    # Expect common to be drawn ~99% of the time, definitely > 90%
    self.assertGreater(common_count, draws * 0.90)

  def test_sample_words_dispatch(self):
    words = ['a', 'b', 'c']
    counts = {'a': 100, 'b': 1, 'c': 1}

    # Uniform sampling does not favor 'a'
    uniform_drawn = sample_words(words, counts, k=1, weighted=False)
    self.assertEqual(len(uniform_drawn), 1)

    # Weighted sampling favors 'a'
    a_count = sum(1 for _ in range(100) if sample_words(words, counts, k=1, weighted=True) == ['a'])
    self.assertGreater(a_count, 70)
