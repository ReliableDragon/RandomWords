import unittest

from unittest.mock import MagicMock

from command import OVERWRITE_FILE_QUESTION
from command_list import CommandList
from command_manager import CommandManager
from fake_file_manager import FakeFileManager
from save_cmd import Save


class SaveTest(unittest.TestCase):

  def test_matches(self):
    save = Save(MagicMock())
    for line in ['save rare', 'save rare pool', 'SAVE rare']:
      self.assertTrue(save.matches(line), line)
    for line in ['save', 'save rare pool extra']:
      self.assertFalse(save.matches(line), line)

  ###
  ### one argument: the active pool
  ###

  def test_execute_writes_the_active_pool(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      result = save.execute(['rare'], {'words': ['a', 'b', 'c']})

      self.assertTrue(result.ok)
      self.assertFalse(result.confirm)
      self.assertEqual(result.message, 'Wrote 3 words to custom/rare.txt.')
      self.assertEqual(result.data,
                       {'name': 'rare', 'pool': 'words', 'size': 3,
                        'path': 'custom/rare.txt'})
      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['a', 'b', 'c'])

  def test_execute_without_an_active_pool_fails(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      result = save.execute(['rare'], {})

      self.assertFalse(result.ok)
      self.assertIn('nothing to write', result.message)
      self.assertFalse(tfm.pool_exists('rare'))

  ###
  ### two arguments: a named pool
  ###

  def test_execute_writes_a_named_pool(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      context = {'words': ['a'], 'moby': ['whale', 'harpoon']}
      result = save.execute(['rare', 'moby'], context)

      self.assertTrue(result.ok)
      self.assertEqual(result.data['pool'], 'moby')
      self.assertCountEqual(tfm.get_words('custom/rare.txt'),
                            ['whale', 'harpoon'])

  def test_execute_refuses_an_unknown_pool_name(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      context = {'words': ['a'], 'moby': ['whale']}
      result = save.execute(['rare', 'nope'], context)

      self.assertFalse(result.ok)
      self.assertIn('"nope" is not a saved pool', result.message)
      self.assertIn('moby', result.message)
      self.assertFalse(tfm.pool_exists('rare'))

  def test_execute_an_empty_named_pool_fails(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      context = {'words': ['a'], 'empty': []}
      result = save.execute(['rare', 'empty'], context)

      self.assertFalse(result.ok)
      self.assertIn('has no words', result.message)
      self.assertFalse(tfm.pool_exists('rare'))

  ###
  ### the overwrite question
  ###

  def test_execute_asks_before_overwriting(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      save.execute(['rare'], {'words': ['a', 'b']})

      result = save.execute(['rare'], {'words': ['x', 'y', 'z']})

      self.assertTrue(result.ok)
      self.assertEqual(result.confirm, OVERWRITE_FILE_QUESTION)
      self.assertIsNotNone(result.on_confirm)
      # The command reports what needs asking; it neither writes nor
      # decides. The file on disk is untouched until something calls the
      # callback it handed back.
      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['a', 'b'])

  def test_a_refused_write_leaves_the_disk_untouched(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      save.execute(['rare'], {'words': ['a', 'b']})

      # Asking, and then simply never calling the confirm callback, is what
      # a "no" looks like on both front ends: the terminal never calls
      # CommandManager.apply, and the browser never repeats the request
      # with force.
      save.execute(['rare'], {'words': ['x', 'y', 'z']})

      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['a', 'b'])

  def test_confirming_runs_the_callback_and_writes_the_new_words(self):
    with FakeFileManager() as tfm:
      save = Save(tfm)
      save.execute(['rare'], {'words': ['a', 'b']})
      result = save.execute(['rare'], {'words': ['x', 'y', 'z']})

      message = result.on_confirm()

      self.assertEqual(message, 'Wrote 3 words to custom/rare.txt.')
      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['x', 'y', 'z'])

  ###
  ### through the manager: both the immediate write and the confirmed one
  ###

  def test_through_the_manager_a_new_pool_writes_immediately(self):
    with FakeFileManager() as tfm:
      cl = CommandList(tfm)
      cm = CommandManager(cl, context={'words': ['a', 'b']})
      cm.initialize_commands()

      result = cm.execute(cl.get_cmd('save'), ['rare'])

      self.assertTrue(result.ok)
      self.assertFalse(result.confirm)
      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['a', 'b'])

  def test_through_the_manager_apply_performs_the_confirmed_write(self):
    # CommandManager.apply is the one place both front ends' yes arrives:
    # the terminal calls it directly, and the browser's forced retry
    # reaches it through apply_if_forced. Either way, this is what actually
    # writes the file once the answer is known.
    with FakeFileManager() as tfm:
      cl = CommandList(tfm)
      cm = CommandManager(cl, context={'words': ['a', 'b']})
      cm.initialize_commands()
      save_cmd = cl.get_cmd('save')
      cm.execute(save_cmd, ['rare'])

      cm.context['words'] = ['x', 'y', 'z']
      asked = cm.execute(save_cmd, ['rare'])
      self.assertEqual(asked.confirm, OVERWRITE_FILE_QUESTION)
      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['a', 'b'])

      applied = cm.apply(asked)

      self.assertTrue(applied.ok)
      self.assertFalse(applied.confirm)
      self.assertEqual(applied.message, 'Wrote 3 words to custom/rare.txt.')
      self.assertCountEqual(tfm.get_words('custom/rare.txt'), ['x', 'y', 'z'])
