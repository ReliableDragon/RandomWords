import unittest
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock

import file_manager
from ls_cmd import LS
from test_util import make_mock_file

class TestLS(unittest.TestCase):

  def test_execute(self):
    fm = MagicMock(spec=file_manager.FileManager)
    f1 = make_mock_file('aaa')
    f2 = make_mock_file('bbb')
    fm.ls.return_value = [f1, f2]

    f = io.StringIO()
    with redirect_stdout(f):
      ls = LS(fm)
      ls.execute([], None)
      
    self.assertEqual(f.getvalue(), 'aaa\nbbb\n')
