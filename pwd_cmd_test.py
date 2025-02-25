import unittest
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock

from pwd_cmd import PWD
from file_manager import FileManager
from test_file_manager import TestFileManager

class PWDTest(unittest.TestCase):
  
  def test_execute(self):
    with TestFileManager() as tfm:
      tfm.dir = '/pronk/norbisk/'
      pwd = PWD(tfm)

      f = io.StringIO()
      with redirect_stdout(f):
        pwd.execute([], None)
        
      self.assertEqual(f.getvalue(), '/pronk/norbisk/\n')
