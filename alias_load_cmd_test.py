import unittest

from unittest.mock import MagicMock

from fake_file_manager import FakeFileManager
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
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      result = al.execute(['dooble', tfm.td.tf1_name], {})
      self.assertIn('dooble', result.updates)
      self.assertCountEqual(result.updates['dooble'], ['a', 'b', 'c'])
      self.assertFalse(result.confirm)

  def test_execute_context_read(self):
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      result = al.execute(['dooble'], {'words': ['1', '2', '3']})
      self.assertIn('dooble', result.updates)
      self.assertCountEqual(result.updates['dooble'], ['1', '2', '3'])

  def test_execute_existing_alias_asks_first(self):
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      context = {'words': ['1', '2', '3'], 'dooble': ['old']}

      result = al.execute(['dooble'], context)

      # The command neither asks nor applies; it reports what needs asking.
      self.assertEqual(result.confirm, 'Alias exists. Overwrite? y/N')
      self.assertCountEqual(result.updates['dooble'], ['1', '2', '3'])
      self.assertEqual(context['dooble'], ['old'])

  def test_execute_missing_file(self):
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      result = al.execute(['dooble', 'no_such_file.txt'], {})
      self.assertFalse(result.ok)
      self.assertIn('alias not created', result.message)

  def test_execute_without_words(self):
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      result = al.execute(['dooble'], {})
      self.assertFalse(result.ok)
      self.assertIn('nothing to save', result.message)

  def test_execute_refuses_a_name_the_language_cannot_spell(self):
    # The API reaches execute() without passing the command syntax, so a
    # name with a space or a slash would otherwise create a pool that no
    # terminal command could ever refer to again.
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      for name in ['has space', 'a/b', 'a.txt', 'a-b']:
        with self.subTest(name=name):
          result = al.execute([name], {'words': ['a']})
          self.assertFalse(result.ok)
          self.assertIn('cannot be a pool name', result.message)

  def test_execute_allows_ordinary_names(self):
    with FakeFileManager() as tfm:
      al = AliasLoad(tfm)
      for name in ['moby', 'pool_2', 'A1']:
        with self.subTest(name=name):
          self.assertTrue(al.execute([name], {'words': ['a']}).ok)
