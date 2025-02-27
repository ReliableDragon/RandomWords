import unittest

from unittest.mock import MagicMock

from test_file_manager import TestFileManager
from alias_load_cmd import AliasLoad

class AliasLoadTest(unittest.TestCase):

  def test_matches(self):
    al = AliasLoad(MagicMock())
    self.assertTrue(al.matches('al d f.txt'))
    self.assertTrue(al.matches('alias_load asdf_asdf qwery/qwerty/qwerty.txt')) 
    self.assertTrue(al.matches('alias bb'))
    self.assertFalse(al.matches('al aa/bb/cc.txt'))
    self.assertFalse(al.matches('alias_load one two three'))
    self.assertFalse(al.matches('alias'))

  def test_parse_args(self):
    al = AliasLoad(MagicMock())
    self.assertEqual(al.parse_args('al a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('alias a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('alias_load one two'), ['one', 'two'])

  def test_execute(self):
    with TestFileManager() as tfm:
      al = AliasLoad(tfm)
      result = al.execute(['dooble', tfm.td.tf1_name], {})
      self.assertTrue('dooble' in result)
      self.assertCountEqual(result['dooble'], ['a', 'b', 'c'])

  def test_execute_context_read(self):
    with TestFileManager() as tfm:
      al = AliasLoad(tfm)
      result = al.execute(['dooble'], {'words': ['1', '2', '3']})
      self.assertTrue('dooble' in result)
      self.assertCountEqual(result['dooble'], ['1', '2', '3'])

