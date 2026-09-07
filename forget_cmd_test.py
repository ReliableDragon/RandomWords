import unittest

from command_list import CommandList
from command_manager import CommandManager
from fake_file_manager import FakeFileManager
from forget_cmd import Forget


class ForgetTest(unittest.TestCase):

  def test_matches(self):
    forget = Forget()
    for line in ['forget foo', 'rm foo', 'RM foo_bar']:
      self.assertTrue(forget.matches(line), line)
    for line in ['forget', 'rm', 'rm a/b', 'forget one two']:
      self.assertFalse(forget.matches(line), line)

  def test_execute_removes_a_pool(self):
    result = Forget().execute(['spare'], {'words': ['a'], 'spare': ['b']})

    self.assertTrue(result.ok)
    self.assertEqual(result.removes, ['spare'])
    self.assertEqual(result.message, 'Forgot spare.')

  def test_execute_refuses_an_unknown_pool(self):
    result = Forget().execute(['nope'], {'words': ['a']})
    self.assertFalse(result.ok)
    self.assertIn('no pool called nope', result.message)

  def test_execute_refuses_the_active_pool(self):
    result = Forget().execute(['words'], {'words': ['a']})
    self.assertFalse(result.ok)
    self.assertIn('cannot be forgotten', result.message)

  def test_the_manager_applies_the_removal(self):
    with FakeFileManager() as tfm:
      cl = CommandList(tfm)
      cm = CommandManager(cl, context={'words': ['a'], 'spare': ['b']})
      cm.initialize_commands()

      cm.execute(cl.get_cmd('forget'), ['spare'])

      self.assertNotIn('spare', cm.context)
      self.assertIn('words', cm.context)

  def test_a_refused_removal_changes_nothing(self):
    with FakeFileManager() as tfm:
      cl = CommandList(tfm)
      cm = CommandManager(cl, context={'words': ['a'], 'spare': ['b']})
      cm.initialize_commands()

      cm.execute(cl.get_cmd('forget'), ['words'])

      self.assertIn('words', cm.context)
      self.assertIn('spare', cm.context)
