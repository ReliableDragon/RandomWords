import os
import unittest

from command_list import CommandList
from command_manager import CommandManager
from fake_file_manager import FakeFileManager
from file_manager import InvalidPath
from parser import Parser


# Every way a path could name something outside the library. These run
# through the real parser and command manager rather than against the
# resolver directly, because the guarantee that matters is the one a user
# request gets, not the one a unit call gets.
ESCAPES = [
  '/etc/passwd',
  '/',
  '..',
  '../..',
  '../etc/passwd',
  '../../../etc/passwd',
  'myth/../../etc/passwd',
  './../etc',
]


class PathSafetyTest(unittest.TestCase):

  def run_line(self, tfm, line):
    cl = CommandList(tfm)
    cm = CommandManager(cl, context={'pool': ['a', 'b']})
    cm.initialize_commands()
    cmd, args_ = Parser(cl).parse(line)
    if cmd is None:
      # Nothing claimed the line, so nothing can act on it.
      return None
    return cm.execute(cmd, args_)

  def test_no_command_can_read_outside_the_library(self):
    with FakeFileManager() as tfm:
      for escape in ESCAPES:
        for template in ['load {}', 'ls {}', 'r {}', 'mul {}',
                         'al saved {}', 'd pool {} out', 'i pool {} out',
                         'c pool {} out', 'save {} pool']:
          line = template.format(escape)
          with self.subTest(line=line):
            result = self.run_line(tfm, line)
            if result is None:
              continue
            self.assertFalse(
                result.ok,
                f'{line!r} was accepted; it must be refused')
            self.assertFalse(
                result.updates,
                f'{line!r} changed the session')

  # save's only path-shaped argument is the name it writes under, which
  # write_path validates by shape rather than by resolving it, so this
  # covers the same guarantee through that other door: every escape is
  # still refused, and -- the thing test_no_command_can_read_outside_the_
  # library above cannot see -- nothing ever reaches disk, not even the
  # custom/ folder that a real write would create.
  def test_save_cannot_write_outside_the_library(self):
    with FakeFileManager() as tfm:
      for escape in ESCAPES:
        with self.subTest(escape=escape):
          result = self.run_line(tfm, f'save {escape} pool')
          self.assertIsNotNone(result, f'{escape!r} was not even recognised')
          self.assertFalse(result.ok, f'{escape!r} was accepted as a name')
      self.assertFalse(os.path.exists(os.path.join(tfm.root, 'custom')))

  def test_resolver_rejects_each_escape(self):
    with FakeFileManager() as tfm:
      for escape in ESCAPES:
        with self.subTest(path=escape):
          with self.assertRaises(InvalidPath):
            tfm.resolve(escape)

  def test_resolver_rejects_a_symlink_leading_out(self):
    with FakeFileManager() as tfm:
      outside = os.path.dirname(os.path.realpath(tfm.root))
      os.symlink(outside, os.path.join(tfm.root, 'escape'))

      with self.assertRaises(InvalidPath):
        tfm.resolve('escape')
      with self.assertRaises(InvalidPath):
        tfm.resolve('escape/anything.txt')

  def test_a_legitimately_deep_path_is_allowed(self):
    with FakeFileManager() as tfm:
      # The guard must not be so blunt that it refuses real files.
      self.assertCountEqual(tfm.get_words(tfm.td.tf3_path),
                            ['robophicles', 'aeschylinux', 'euripidos'])

  def test_the_root_itself_resolves(self):
    with FakeFileManager() as tfm:
      self.assertEqual(tfm.resolve(''), tfm.root)
      self.assertEqual(tfm.relative(tfm.root), '')
