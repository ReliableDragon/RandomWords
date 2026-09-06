import io
import unittest

from contextlib import redirect_stdout

from dump_cmd import Dump


class DumpTest(unittest.TestCase):

  def test_execute_lists_names_and_sizes(self):
    f = io.StringIO()
    with redirect_stdout(f):
      Dump().execute([], {'words': ['a', 'b'], 'foo': ['c']})
    self.assertEqual(f.getvalue(), 'words (active pool): 2 words\nfoo: 1 words\n')

  def test_execute_empty(self):
    f = io.StringIO()
    with redirect_stdout(f):
      Dump().execute([], {})
    self.assertEqual(f.getvalue(), 'Nothing is loaded.\n')

  def test_execute_all_prints_contents(self):
    f = io.StringIO()
    with redirect_stdout(f):
      Dump().execute(['all'], {'foo': ['c']})
    self.assertIn("'foo': ['c']", f.getvalue())

  def test_execute_other_arg_does_not_dump_contents(self):
    f = io.StringIO()
    with redirect_stdout(f):
      Dump().execute(['false'], {'foo': ['c']})
    self.assertEqual(f.getvalue(), 'foo: 1 words\n')
