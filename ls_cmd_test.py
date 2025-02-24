import unittest
import io

from contextlib import redirect_stdout
from unittest.mock import MagicMock

from file_manager import FileManager
from ls_cmd import LS
from test_util import make_mock_file
from test_directories import TestDirectories

def get_files(ls_str):
  return ls_str.split('\n')[:-1]

class TestLS(unittest.TestCase):

  def test_execute(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      TestDirectories() as td):
      fm = FileManager(td.root)
      ls = LS(fm)
      ls.execute([], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.d2_name, td.tf1_name])

  def test_execute_with_arg(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      TestDirectories() as td):
      fm = FileManager(td.root)
      ls = LS(fm)
      ls.execute([td.root], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.d2_name, td.tf1_name])

  def test_execute_with_arg_subdir(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      TestDirectories() as td):
      fm = FileManager(td.root)
      ls = LS(fm)
      ls.execute([td.d2_name], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.d3_name, td.d4_name, td.tf2_name])

  def test_execute_with_arg_diff_dir(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      TestDirectories() as td):
      fm = FileManager(td.d4.name)
      ls = LS(fm)
      ls.execute([td.d3.name], None)
      
      self.assertCountEqual(get_files(f.getvalue()), [td.tf3_name, td.tf4_name])

  def test_execute_with_arg_err(self):
    f = io.StringIO()
    with (
      redirect_stdout(f),
      TestDirectories() as td):
      fm = FileManager(td.d4.name)
      ls = LS(fm)
      ls.execute(['shmooble/'], None)
      
      self.assertEqual(f.getvalue(), f"File '{fm.dir}shmooble/' not found.\n")
