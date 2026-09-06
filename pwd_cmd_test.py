import unittest
import io

from contextlib import redirect_stdout

from pwd_cmd import PWD
from fake_file_manager import FakeFileManager

class PWDTest(unittest.TestCase):
  
  def test_execute(self):
    with FakeFileManager() as tfm:
      tfm.dir = '/pronk/norbisk/'
      pwd = PWD(tfm)

      f = io.StringIO()
      with redirect_stdout(f):
        pwd.execute([], None)
        
      self.assertEqual(f.getvalue(), '/pronk/norbisk/\n')
