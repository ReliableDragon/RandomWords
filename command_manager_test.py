import unittest

from unittest.mock import MagicMock, patch

from command_manager import CommandManager
from command_list import CommandList
from file_manager import FileManager
from test_command import TestCommand

class CommandManagerTest(unittest.TestCase):

  def test_initialize_commands(self):
    test_command = TestCommand()
    cl = MagicMock(spec=CommandList)
    with patch.object(cl, 'cmd_list', return_value=[test_command]):
      cm = CommandManager(cl)

      cm.initialize_commands()
      
      cl.init_cmd.assert_called_once_with(test_command)


  def test_execute(self):
    test_command = TestCommand()
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={'test_key': 1000})

    result = cm.execute(test_command, ['abc', 2])

    self.assertEqual(cm.context, {'test_key': 24601})
    self.assertEqual(result, 'abcabc')


  def test_execute_err(self):
    test_command = TestCommand()
    cl = MagicMock(spec=CommandList)
    cm = CommandManager(cl, context={'test_key': 1000})

    with self.assertRaises(ValueError):
      result = cm.execute(test_command, [1, 2])


  def test_initialize_and_execute(self):
    test_command = TestCommand()
    with patch.object(CommandList, 'cmd_list', return_value=[test_command]):
      fm = MagicMock(spec=FileManager)
      cl = CommandList(fm)
      cm = CommandManager(cl)

      cm.initialize_commands()
      result = cm.execute(test_command, ['abc', 2])

      self.assertEqual(cm.context, {'test_key': 24601})
      self.assertEqual(result, 'abcabc')
