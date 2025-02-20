import unittest
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock

from pwd_cmd import PWD
from file_manager import FileManager

class CDTest(unittest.TestCase):
  
  def test_execute(self):
    fm = MagicMock(spec=FileManager)
    fm.pwd.return_value = 'pronk/norbisk'
    pwd = PWD(fm)

    f = io.StringIO()
    with redirect_stdout(f):
      pwd.execute([], None)
      
    self.assertEqual(f.getvalue(), 'pronk/norbisk\n')
    fm.pwd.assert_called_once()
