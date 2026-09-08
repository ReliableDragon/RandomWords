import unittest

from unittest.mock import MagicMock, patch

from command_manager import CommandManager
from command_list import CommandList
from command_result import CommandResult
from file_manager import FileManager, InvalidPath
from fake_command import FakeCommand

class CommandManagerTest(unittest.TestCase):

  def test_initialize_commands(self):
    test_command = FakeCommand()
    cl = MagicMock(spec=CommandList)
    with patch.object(cl, 'cmd_list', return_value=[test_command]):
      cm = CommandManager(cl)

      cm.initialize_commands()
      
      cl.init_cmd.assert_called_once_with(test_command)


  def test_execute(self):
    test_command = FakeCommand()
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={'test_key': 1000})

    result = cm.execute(test_command, ['abc', 2])

    self.assertEqual(cm.context, {'test_key': 24601})
    self.assertEqual(result.message, 'abcabc')


  def test_execute_err(self):
    test_command = FakeCommand()
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={'test_key': 1000})

    with self.assertRaises(ValueError):
      cm.execute(test_command, [1, 2])


  def test_initialize_and_execute(self):
    test_command = FakeCommand()
    with patch.object(CommandList, 'cmd_list', return_value=[test_command]):
      fm = MagicMock(spec=FileManager)
      cl = CommandList(fm)
      cm = CommandManager(cl)

      cm.initialize_commands()
      result = cm.execute(test_command, ['abc', 2])

      self.assertEqual(cm.context, {'test_key': 24601})
      self.assertEqual(result.message, 'abcabc')

  ###
  ### apply: the one place a confirmation, from either front end, arrives
  ###

  def test_apply_merges_updates_when_there_is_no_on_confirm(self):
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={})
    result = CommandResult(updates={'saved': ['a']})

    applied = cm.apply(result)

    self.assertEqual(cm.context, {'saved': ['a']})
    self.assertIs(applied, result)

  def test_apply_does_nothing_for_a_failed_result(self):
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={})
    result = CommandResult.fail('nope')

    cm.apply(result)

    self.assertEqual(cm.context, {})

  def test_apply_runs_on_confirm_once_the_answer_is_yes(self):
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={})
    calls = []
    def do_the_write():
      calls.append(1)
      return 'Wrote 3 words to custom/rare.txt.'
    result = CommandResult(confirm='File exists. Overwrite? y/N',
                           on_confirm=do_the_write)

    applied = cm.apply(result)

    self.assertEqual(calls, [1])
    self.assertTrue(applied.ok)
    self.assertFalse(applied.confirm)
    self.assertEqual(applied.message, 'Wrote 3 words to custom/rare.txt.')

  def test_apply_reports_a_failure_from_on_confirm(self):
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={})
    def fail_the_write():
      raise InvalidPath('bad name')
    result = CommandResult(confirm='File exists. Overwrite? y/N',
                           on_confirm=fail_the_write)

    applied = cm.apply(result)

    self.assertFalse(applied.ok)
    self.assertEqual(applied.message, 'bad name')
