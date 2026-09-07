import unittest

from cd_cmd import CD
from fake_file_manager import FakeFileManager

class CDTest(unittest.TestCase):

  def test_execute(self):
    with FakeFileManager() as tfm:
      cd = CD(tfm)

      cd.execute([tfm.td.d2.name], None)

      self.assertEqual(tfm.dir, tfm.td.d2.name + '/')

  def test_execute_missing_folder(self):
    with FakeFileManager() as tfm:
      cd = CD(tfm)
      before = tfm.dir

      result = cd.execute(['no_such_folder'], None)

      self.assertEqual(tfm.dir, before)
    self.assertFalse(result.ok)
    self.assertIn('No such folder', result.message)
