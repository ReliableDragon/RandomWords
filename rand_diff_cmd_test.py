import io
import os
import unittest

from contextlib import redirect_stdout
from unittest.mock import patch

from command_list import CommandList
from command_manager import CommandManager
from fake_file_manager import FakeFileManager


class RandDiffTest(unittest.TestCase):

  def make_dict(self, root, size, contents):
    dicts = os.path.join(root, 'dicts')
    os.makedirs(dicts, exist_ok=True)
    with open(os.path.join(dicts, f'{size}k_words.txt'), 'w') as f:
      f.write(contents)

  @patch('random.choice')
  def test_execute(self, mock_choice):
    with FakeFileManager() as tfm:
      # tf4 holds 'one two three' plus digits; the dictionary holds two of them.
      self.make_dict(tfm.td.root, '10', 'one\ntwo\n')
      mock_choice.side_effect = lambda seq: tfm.td.tf4.name

      cl = CommandList(tfm)
      # A stale pool: the old implementation diffed this instead of the
      # file it had just loaded.
      cm = CommandManager(cl, context={'words': ['stale']})
      cm.initialize_commands()

      with (redirect_stdout(io.StringIO()),
        patch('file_manager.ROOT_DIR', tfm.td.root)):
        cm.execute(cl.get_cmd('rand_diff'), ['10'])

      self.assertEqual(cm.context['words'], ['three'])

  @patch('random.choice')
  def test_execute_default_dictionary(self, mock_choice):
    with FakeFileManager() as tfm:
      self.make_dict(tfm.td.root, '70', 'one\n')
      mock_choice.side_effect = lambda seq: tfm.td.tf4.name

      cl = CommandList(tfm)
      cm = CommandManager(cl)
      cm.initialize_commands()

      with (redirect_stdout(io.StringIO()),
        patch('file_manager.ROOT_DIR', tfm.td.root)):
        cm.execute(cl.get_cmd('rand_diff'), [])

      self.assertCountEqual(cm.context['words'], ['two', 'three'])

  def test_matches(self):
    cl = CommandList(FakeFileManager())
    cm = CommandManager(cl)
    cm.initialize_commands()
    rd = cl.get_cmd('rand_diff')

    self.assertTrue(rd.matches('rd'))
    self.assertTrue(rd.matches('rand_diff 450'))
    self.assertFalse(rd.matches('rd 42'))

  @patch('random.choice')
  def test_execute_no_files(self, mock_choice):
    f = io.StringIO()
    with FakeFileManager() as tfm:
      empty = os.path.join(tfm.td.root, 'empty')
      os.mkdir(empty)
      tfm.dir = empty + '/'

      cl = CommandList(tfm)
      cm = CommandManager(cl)
      cm.initialize_commands()

      with redirect_stdout(f):
        result = cm.execute(cl.get_cmd('rand_diff'), ['10'])

      self.assertIsNone(result)
      self.assertNotIn('words', cm.context)
    self.assertIn('No .txt files found', f.getvalue())
