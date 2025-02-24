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
    f1 = make_mock_file('aaa', is_dir=True)
    f2 = make_mock_file('bbb')
    fm.ls.return_value = [f1, f2]

    f = io.StringIO()
    with redirect_stdout(f):
      ls = LS(fm)
      ls.execute([], None)
      
    self.assertEqual(f.getvalue(), 'aaa/\nbbb\n')

  def test_execute_with_arg(self):
    fm = MagicMock(spec=file_manager.FileManager)
    f1 = make_mock_file('aaa', is_dir=True)
    f2 = make_mock_file('bbb')
    fm.ls.return_value = [f2]

    f = io.StringIO()
    with redirect_stdout(f):
      ls = LS(fm)
      ls.execute(['aaa'], None)
      
    self.assertEqual(f.getvalue(), 'bbb\n')
    fm.ls.assert_called_once_with('aaa')

  def test_execute_with_arg(self):
    f = io.StringIO()
    with redirect_stdout(f):
      fm = file_manager.FileManager('shmoogle/')
      ls = LS(fm)
      ls.execute(['aaa'], None)
      
    self.assertEqual(f.getvalue(), "File 'shmoogle/aaa' not found.\n")
