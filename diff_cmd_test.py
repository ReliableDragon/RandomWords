import unittest

from unittest.mock import MagicMock

from fake_file_manager import FakeFileManager
from diff_cmd import Diff

class DiffCommandTest(unittest.TestCase):

  def test_matches(self):
    al = Diff(MagicMock())
    self.assertTrue(al.matches('d d f.txt'))
    self.assertTrue(al.matches('diff asdf_asdf qwery/qwerty/qwerty.txt'))
    self.assertTrue(al.matches('d one two three'))
    self.assertTrue(al.matches('d bb'))
    self.assertFalse(al.matches('d'))
    self.assertTrue(al.matches('d aa/bb/cc.txt'))
    self.assertFalse(al.matches('d one two three four'))

  def test_parse_args(self):
    al = Diff(MagicMock())
    self.assertEqual(al.parse_args('d a b'), ['a', 'b'])
    self.assertEqual(al.parse_args('d one two three'), ['one', 'two', 'three'])

  def test_execute(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['spenoik', tfm.td.tf1_name], {'spenoik': ['b', 'c', 'd']})
      self.assertIn('spenoik', result.updates)
      self.assertCountEqual(result.updates['spenoik'], ['d'])

  def test_execute_three_arg(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['halmenk', tfm.td.tf1_name, 'dilau'], {'halmenk': ['b', 'c', 'd']})
      self.assertIn('dilau', result.updates)
      self.assertCountEqual(result.updates['dilau'], ['d'])

  def test_execute_two_aliases(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['bleenu', 'turp', 'blizztu'], {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']})
      self.assertIn('blizztu', result.updates)
      self.assertCountEqual(result.updates['blizztu'], ['1', '2'])

  def test_execute_two_files_rooting(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute([tfm.td.tf1_name, tfm.td.tf5_path, 'erbint'], {})
      self.assertIn('erbint', result.updates)
      self.assertCountEqual(result.updates['erbint'], ['a', 'b', 'c'])

  def test_execute_two_args_err(self):
    # With two arguments the result is written back to the first one, so a
    # first argument that is not a saved pool is a user error, not a crash.
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute([tfm.td.tf5_path, tfm.td.tf1_name], {})
      self.assertFalse(result.ok)
    self.assertIn('is not a saved pool', result.message)

  def test_execute_one_arg(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      result = al.execute(['bleenu'], {'bleenu': ['1', '2', '3'], 'words': ['3', '4', '5']})
      self.assertIn('words', result.updates)
      self.assertCountEqual(result.updates['words'], ['4', '5'])

  # ---------- the ask/don't-ask matrix ----------

  def test_execute_one_arg_never_asks(self):
    # Writing back to the active pool is what the one-argument form means,
    # not a mistake to guard against, even though 'words' already exists.
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'words': ['1', '2', '3'], 'bleenu': ['3', '4', '5']}
      result = al.execute(['bleenu'], context)
      self.assertFalse(result.confirm)
      self.assertIn('words', result.updates)

  def test_execute_two_arg_never_asks(self):
    # Writing back to the first operand is what the two-argument form
    # means; that overwrite is documented, not a surprise to confirm.
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']}
      result = al.execute(['bleenu', 'turp'], context)
      self.assertFalse(result.confirm)
      self.assertIn('bleenu', result.updates)

  def test_execute_three_arg_fresh_name_never_asks(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']}
      result = al.execute(['bleenu', 'turp', 'fresh'], context)
      self.assertFalse(result.confirm)
      self.assertIn('fresh', result.updates)

  def test_execute_three_arg_existing_out_asks_first(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5'],
                 'dilau': ['old']}

      result = al.execute(['bleenu', 'turp', 'dilau'], context)

      # The command neither asks nor applies; it reports what needs asking,
      # and the context stays as it was until a front end brings back a yes.
      self.assertEqual(result.confirm, 'Alias exists. Overwrite? y/N')
      self.assertCountEqual(result.updates['dilau'], ['1', '2'])
      self.assertEqual(context['dilau'], ['old'])

  def test_execute_three_arg_out_same_as_first_never_asks(self):
    # Naming the first operand as the explicit third argument is just the
    # two-argument form spelled out, so it does not ask either.
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'bleenu': ['1', '2', '3'], 'turp': ['3', '4', '5']}
      result = al.execute(['bleenu', 'turp', 'bleenu'], context)
      self.assertFalse(result.confirm)
      self.assertIn('bleenu', result.updates)

  # ---------- empty operands ----------

  def test_execute_empty_first_operand_fails(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'empty': [], 'turp': ['3', '4', '5']}
      result = al.execute(['empty', 'turp'], context)
      self.assertFalse(result.ok)
      self.assertFalse(result.updates)
      self.assertIn('empty', result.message)

  def test_execute_empty_second_operand_fails(self):
    with FakeFileManager() as tfm:
      al = Diff(tfm)
      context = {'turp': ['3', '4', '5'], 'empty': []}
      result = al.execute(['turp', 'empty'], context)
      self.assertFalse(result.ok)
      self.assertFalse(result.updates)
      self.assertIn('empty', result.message)

