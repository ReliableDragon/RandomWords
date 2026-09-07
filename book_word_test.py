import io
import unittest

from contextlib import redirect_stdout
from unittest.mock import patch

from book_word import RandomWords
from command_list import CommandList
from command_manager import CommandManager
from fake_file_manager import FakeFileManager
from parser import Parser


class RandomWordsTest(unittest.TestCase):

  def build(self, tfm):
    cl = CommandList(tfm)
    cm = CommandManager(cl)
    cm.initialize_commands()
    return RandomWords(tfm, Parser(cl), cm), cl, cm

  def test_run_loads_and_quits(self):
    with FakeFileManager() as tfm:
      rw, _, cm = self.build(tfm)
      with (patch('builtins.input', side_effect=['quit']),
        redirect_stdout(io.StringIO())):
        rw.run(tfm.td.tf1_path)
      self.assertCountEqual(cm.context['words'], ['a', 'b', 'c'])

  def test_run_exits_on_eof(self):
    with FakeFileManager() as tfm:
      rw, _, _ = self.build(tfm)
      with (patch('builtins.input', side_effect=EOFError),
        redirect_stdout(io.StringIO())):
        rw.run(tfm.td.tf1_path)

  def test_run_exits_on_interrupt(self):
    with FakeFileManager() as tfm:
      rw, _, _ = self.build(tfm)
      with (patch('builtins.input', side_effect=KeyboardInterrupt),
        redirect_stdout(io.StringIO())):
        rw.run(tfm.td.tf1_path)

  def test_run_survives_a_failing_command(self):
    f = io.StringIO()
    with FakeFileManager() as tfm:
      rw, cl, _ = self.build(tfm)
      victim = cl.get_cmd('help')
      with (patch.object(victim, 'execute', side_effect=RuntimeError('boom')),
        patch('builtins.input', side_effect=['help', 'quit']),
        redirect_stdout(f)):
        rw.run(tfm.td.tf1_path)
    self.assertIn('Error: boom', f.getvalue())

  def test_run_survives_a_missing_startup_file(self):
    f = io.StringIO()
    with FakeFileManager() as tfm:
      rw, _, cm = self.build(tfm)
      with (patch('builtins.input', side_effect=['word', 'quit']),
        redirect_stdout(f)):
        rw.run('no_such_file.txt')
      self.assertNotIn('words', cm.context)
    self.assertIn('No words are loaded', f.getvalue())

  def test_run_reports_an_unresolved_line(self):
    f = io.StringIO()
    with FakeFileManager() as tfm:
      rw, _, _ = self.build(tfm)
      with (patch('builtins.input', side_effect=['zzz nonsense', 'quit']),
        redirect_stdout(f)):
        rw.run(tfm.td.tf1_path)
    self.assertIn("I'm sorry, I don't understand.", f.getvalue())
