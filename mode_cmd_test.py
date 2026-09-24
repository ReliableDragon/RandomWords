import unittest

from command_manager import Context
from mode_cmd import Mode


class ModeTest(unittest.TestCase):

  def test_cmd_name_and_matches(self):
    cmd = Mode()
    self.assertEqual(cmd.cmd_name(), 'mode')
    for line in ['mode', 'mode uniform', 'mode weighted', 'sampling', 'sampling weighted']:
      self.assertTrue(cmd.matches(line), f'Failed to match {line}')
    for line in ['model', 'moderator', 'mood']:
      self.assertFalse(cmd.matches(line), f'Should not match {line}')

  def test_parse_args(self):
    cmd = Mode()
    self.assertEqual(cmd.parse_args('mode'), [])
    self.assertEqual(cmd.parse_args('mode weighted'), ['weighted'])
    self.assertEqual(cmd.parse_args('mode uniform'), ['uniform'])

  def test_execute_query(self):
    cmd = Mode()
    ctx = Context(sampling_mode='uniform')
    res = cmd.execute([], ctx)
    self.assertTrue(res.ok)
    self.assertEqual(res.data['mode'], 'uniform')
    self.assertIn('Sampling mode is uniform', res.message)

  def test_execute_set_mode(self):
    cmd = Mode()
    ctx = Context(sampling_mode='uniform')
    res = cmd.execute(['weighted'], ctx)
    self.assertTrue(res.ok)
    self.assertEqual(res.data['mode'], 'weighted')
    self.assertEqual(ctx.sampling_mode, 'weighted')

    res2 = cmd.execute(['uniform'], ctx)
    self.assertTrue(res2.ok)
    self.assertEqual(res2.data['mode'], 'uniform')
    self.assertEqual(ctx.sampling_mode, 'uniform')

  def test_execute_invalid_mode(self):
    cmd = Mode()
    ctx = Context()
    res = cmd.execute(['superposition'], ctx)
    self.assertFalse(res.ok)
    self.assertIn('Unknown mode', res.message)
