import unittest
import io

from unittest.mock import patch
from contextlib import redirect_stdout

from get_word_cmd import GetWord

class GetWordTest(unittest.TestCase):
  
  @patch('random.choice')
  def test_execute(self, mock_choice):
    mock_choice.side_effect = lambda a: a[0]

    getword = GetWord()

    f = io.StringIO()
    with redirect_stdout(f):
      result = getword.execute([], {'words': ['a', 'b', 'c']})

    self.assertEqual(f.getvalue(), 'a\n')

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

    f = io.StringIO()
    with redirect_stdout(f):
      result = getword.execute([3], {'words': ['a', 'b', 'c']})

    self.assertEqual(f.getvalue(), 'a b c\n')
