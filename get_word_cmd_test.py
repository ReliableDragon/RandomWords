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
      result = getword.execute([], {'words': ['a.txt', 'b.txt', 'c.txt']})

    self.assertEqual(f.getvalue(), 'a.txt\n')
