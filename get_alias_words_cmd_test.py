import unittest
import io

from unittest.mock import patch
from contextlib import redirect_stdout

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
    f = io.StringIO()
    with redirect_stdout(f):
      gaw.execute(['a', 'b'], {'a': ['aa'], 'b': ['bb']})
    self.assertEqual(f.getvalue(), 'aa bb\n')

  def test_execute_err(self):
    gaw = GetAliasWords()
    f = io.StringIO()
    with redirect_stdout(f):
      result = gaw.execute(['a', 'b', 'c'], {'a': ['aa'], 'b': ['bb']})
      self.assertIsNone(result)
    self.assertEqual(f.getvalue(), "Arg c was not found in context! Valid values are ['a', 'b'].\n")
      
  @patch('random.choice')
  def test_execute_rand(self, mock_choice):
    mock_choice.side_effect = lambda a: sorted(a)[-1]
    gaw = GetAliasWords()
    f = io.StringIO()
    with redirect_stdout(f):
      gaw.execute(['a', 'r'], {'a': ['aa'], 'b': ['bb']})
    self.assertEqual(f.getvalue(), 'aa bb\n')

