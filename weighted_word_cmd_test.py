import unittest
from unittest.mock import patch

from command_manager import Context
from weighted_word_cmd import WeightedWord


class WeightedWordTest(unittest.TestCase):

  def test_cmd_name_and_matches(self):
    cmd = WeightedWord()
    self.assertEqual(cmd.cmd_name(), 'weighted_word')
    for line in ['w', 'w 3', 'weighted', 'weighted 5', 'oword', 'oword 2']:
      self.assertTrue(cmd.matches(line), f'Failed to match {line}')
    for line in ['word', 'ww', 'weight', 'r']:
      self.assertFalse(cmd.matches(line), f'Should not match {line}')

  def test_parse_args(self):
    cmd = WeightedWord()
    self.assertEqual(cmd.parse_args('w'), [])
    self.assertEqual(cmd.parse_args('w 5'), [5])
    self.assertEqual(cmd.parse_args('weighted 10'), [10])

  def test_execute_without_words(self):
    cmd = WeightedWord()
    res = cmd.execute([], {})
    self.assertFalse(res.ok)
    self.assertIn('No words are loaded', res.message)

  def test_execute_weighted_draw(self):
    cmd = WeightedWord()
    ctx = Context({'words': ['rare', 'common']},
                  counts={'words': {'rare': 1, 'common': 1000}})
    res = cmd.execute([1], ctx)
    self.assertTrue(res.ok)
    self.assertIn(res.data['drawn'][0], ['rare', 'common'])
    self.assertIn('counts', res.data)
    drawn = res.data['drawn'][0]
    self.assertEqual(res.data['counts'][drawn], {'rare': 1, 'common': 1000}[drawn])

  def test_execute_multi_draw(self):
    cmd = WeightedWord()
    ctx = Context({'words': ['a', 'b', 'c']},
                  counts={'words': {'a': 10, 'b': 20, 'c': 30}})
    res = cmd.execute([2], ctx)
    self.assertTrue(res.ok)
    self.assertEqual(len(res.data['drawn']), 2)
    self.assertEqual(len(set(res.data['drawn'])), 2)
