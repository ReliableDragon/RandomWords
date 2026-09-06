import unittest
import io

from contextlib import redirect_stdout

from file_manager import FileManager
from ls_cmd import LS
from fake_directories import FakeDirectories

def get_files(ls_str):
  return ls_str.split('\n')[:-1]

class TestLS(unittest.TestCase):

  def test_execute(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      FakeDirectories() as td):
      fm = FileManager(td.root)
      ls = LS(fm)
      ls.execute([], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.d2_name, td.tf1_name])

  def test_execute_with_arg(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      FakeDirectories() as td):
      fm = FileManager(td.root)
      ls = LS(fm)
      ls.execute([td.root], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.d2_name, td.tf1_name])

  def test_execute_with_arg_subdir(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      FakeDirectories() as td):
      fm = FileManager(td.root)
      ls = LS(fm)
      ls.execute([td.d2_name], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.d3_name, td.d4_name, td.tf2_name])

  def test_execute_with_arg_diff_dir(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      FakeDirectories() as td):
      fm = FileManager(td.d4.name)
      ls = LS(fm)
      ls.execute([td.d3.name], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.tf3_name, td.tf4_name])

  def test_execute_with_arg_err(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      FakeDirectories() as td):
      fm = FileManager(td.d4.name)
      ls = LS(fm)
      ls.execute(['shmooble/'], {})
      
    self.assertEqual(f.getvalue(), f"File '{fm.dir}shmooble/' not found.\n")

  def test_execute_missing_current_dir_names_it(self):
    f = io.StringIO()
    fm = FileManager('/no/such/place/')
    with redirect_stdout(f):
      LS(fm).execute([], None)
    self.assertEqual(f.getvalue(), "File '/no/such/place/' not found.\n")
