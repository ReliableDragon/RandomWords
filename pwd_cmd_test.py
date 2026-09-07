import unittest

from pwd_cmd import PWD
from fake_file_manager import FakeFileManager

class PWDTest(unittest.TestCase):

  def test_execute(self):
    with FakeFileManager() as tfm:
      tfm.dir = '/pronk/norbisk/'
      pwd = PWD(tfm)

      result = pwd.execute([], None)

      self.assertEqual(result.message, '/pronk/norbisk/')
