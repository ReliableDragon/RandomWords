import unittest

from quit_cmd import Quit


class QuitTest(unittest.TestCase):

  def test_matches(self):
    q = Quit()
    for line in ['quit', 'exit', 'q', 'QUIT', ' q ']:
      self.assertTrue(q.matches(line), line)
    for line in ['quitter', '', 'qq', 'quit now']:
      self.assertFalse(q.matches(line), line)

  def test_execute(self):
    result = Quit().execute([], {})
    self.assertTrue(result.quit)
