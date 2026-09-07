import unittest

from unittest.mock import patch

from get_word_cmd import GetWord

class GetWordTest(unittest.TestCase):

  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: a[0]

    getword = GetWord()

    result = getword.execute([], {'words': ['a', 'b', 'c']})

    self.assertEqual(result.message, 'a')
    self.assertEqual(result.data, {'drawn': ['a']})

  @patch('random.choice')
  def test_execute_multi(self, mock_choice):
    num = 0
    def choice(a):
      nonlocal num
      result = a[num]
      num += 1
      return result
    mock_choice.side_effect = choice

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
