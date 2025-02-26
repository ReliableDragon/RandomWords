import unittest

from unittest.mock import MagicMock

from cd_cmd import CD
from test_file_manager import TestFileManager

class CDTest(unittest.TestCase):
  
  def test_execute(self):
    with TestFileManager() as tfm:
      cd = CD(tfm)

      cd.execute([tfm.td.d2.name], None)

      self.assertEqual(tfm.dir, tfm.td.d2.name + '/')
