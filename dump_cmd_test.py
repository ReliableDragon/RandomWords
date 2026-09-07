import unittest

from dump_cmd import Dump


class DumpTest(unittest.TestCase):

  def test_execute_lists_names_and_sizes(self):
    result = Dump().execute([], {'words': ['a', 'b'], 'foo': ['c']})
    self.assertEqual(result.message, 'words (active pool): 2 words\nfoo: 1 words')
    self.assertEqual(result.data, {'pools': [{'name': 'words', 'size': 2}, {'name': 'foo', 'size': 1}]})

  def test_execute_empty(self):
    result = Dump().execute([], {})
    self.assertEqual(result.message, 'Nothing is loaded.')

  def test_execute_all_prints_contents(self):
    result = Dump().execute(['all'], {'foo': ['c']})
    self.assertIn("'foo': ['c']", result.message)

  def test_execute_other_arg_does_not_dump_contents(self):
    result = Dump().execute(['false'], {'foo': ['c']})
    self.assertEqual(result.message, 'foo: 1 words')
