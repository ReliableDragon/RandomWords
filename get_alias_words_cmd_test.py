import unittest

from unittest.mock import patch

from get_alias_words_cmd import GetAliasWords

class GetAliasWordsTest(unittest.TestCase):

  def test_matches(self):
    gaw = GetAliasWords()
    self.assertTrue(gaw.matches('gaw asdf asdf sadf'))
    self.assertTrue(gaw.matches('gaw a'))
    self.assertTrue(gaw.matches('get_alias_words f f f'))
    self.assertFalse(gaw.matches('gaw'))
    self.assertFalse(gaw.matches('gaw a/b'))

  def test_execute(self):
    gaw = GetAliasWords()
    result = gaw.execute(['a', 'b'], {'a': ['aa'], 'b': ['bb']})
    self.assertEqual(result.message, 'aa bb')

  def test_execute_err(self):
    gaw = GetAliasWords()
    result = gaw.execute(['a', 'b', 'c'], {'a': ['aa'], 'b': ['bb']})
    self.assertFalse(result.ok)
    self.assertEqual(result.message, "Arg c was not found in context! Valid values are ['a', 'b'].")

  @patch('random.choice')
  def test_execute_rand(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]
    gaw = GetAliasWords()
    result = gaw.execute(['a', 'r'], {'a': ['aa'], 'b': ['bb']})
    self.assertEqual(result.message, 'aa bb [a b]')

  @patch('random.choice')
  def test_execute_rand_removes_words(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]
    gaw = GetAliasWords()
    result = gaw.execute(['a', 'r'], {'a': ['aa'], 'b': ['bb'], 'words': ['BAD']})
    self.assertEqual(result.message, 'aa bb [a b]')

  def test_execute_rand_without_aliases(self):
    result = GetAliasWords().execute(['r'], {'words': ['a']})
    self.assertFalse(result.ok)
    self.assertIn('No aliases are defined', result.message)

  def test_execute_empty_alias(self):
    result = GetAliasWords().execute(['a'], {'a': []})
    self.assertFalse(result.ok)
    self.assertIn('is empty', result.message)
