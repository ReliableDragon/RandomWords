import os
import unittest

from fake_file_manager import FakeFileManager

class FakeFileManagerTest(unittest.TestCase):

  def test_context_manager(self):
    tfm = FakeFileManager()
    # Outside the context there is no corpus, so listing finds nothing.
    self.assertIsNone(tfm.ls())

    with tfm:
      self.assertIsNotNone(tfm.td)
      self.assertEqual(tfm.root, os.path.realpath(tfm.td.root))
      self.assertIn(tfm.td.tf1_path, tfm.ls())

    # The temporary corpus is gone once the context closes.
    self.assertIsNone(tfm.ls())
