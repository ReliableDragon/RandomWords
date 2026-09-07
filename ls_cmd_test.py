import unittest

from file_manager import FileManager
from ls_cmd import LS
from fake_directories import FakeDirectories

def get_files(message):
  return message.split('\n')

class TestLS(unittest.TestCase):

  def test_execute(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      ls = LS(fm)
      result = ls.execute([], None)

      self.assertCountEqual(get_files(result.message), [td.d2_name, td.tf1_name])

  def test_execute_with_arg(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      ls = LS(fm)
      result = ls.execute([''], None)

      self.assertCountEqual(get_files(result.message), [td.d2_name, td.tf1_name])

  def test_execute_with_arg_subdir(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      ls = LS(fm)
      result = ls.execute([td.d2_name], None)

      self.assertCountEqual(get_files(result.message), [td.d3_name, td.d4_name, td.tf2_name])

  def test_execute_with_arg_diff_dir(self):
    with FakeDirectories() as td:
      fm = FileManager(td.root)
      ls = LS(fm)
      result = ls.execute([td.d3_path], None)

      self.assertCountEqual(get_files(result.message), [td.tf3_name, td.tf4_name])

  def test_execute_with_arg_err(self):
    with FakeDirectories() as td:
      fm = FileManager(td.d4.name)
      ls = LS(fm)
      result = ls.execute(['shmooble/'], {})

    self.assertFalse(result.ok)
    self.assertEqual(result.message, "Folder 'shmooble/' not found.")

  def test_execute_missing_current_dir_names_it(self):
    fm = FileManager('/no/such/place/')
    result = LS(fm).execute([], None)

    self.assertFalse(result.ok)
    self.assertEqual(result.message, "Folder '/' not found.")
