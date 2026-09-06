import unittest
from contextlib import redirect_stdout
import io


from cd_cmd import CD
from fake_file_manager import FakeFileManager

class CDTest(unittest.TestCase):
  
  def test_execute(self):
    with FakeFileManager() as tfm:
      cd = CD(tfm)

      cd.execute([tfm.td.d2.name], None)

      self.assertEqual(tfm.dir, tfm.td.d2.name + '/')

  def test_execute_missing_folder(self):
    f = io.StringIO()
    with FakeFileManager() as tfm:
      cd = CD(tfm)
      before = tfm.dir

      with redirect_stdout(f):
        cd.execute(['no_such_folder'], None)

      self.assertEqual(tfm.dir, before)
    self.assertIn('No such folder', f.getvalue())
