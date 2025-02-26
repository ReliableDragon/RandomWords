import unittest

from test_file_manager import TestFileManager

class TestFileManagerTest(unittest.TestCase):

  def test_context_manager(self):
    tfm = TestFileManager()
    with self.assertRaises(AttributeError):
      tfm.dir.get_rooted()
    self.assertEqual(tfm.dir, 'invalid/')
    with tfm:
      self.assertNotEqual(tfm.dir, '')
      self.assertIsNotNone(tfm.td)
      self.assertIn(tfm.td.tf1.name, tfm.ls())
    self.assertNotEqual(tfm.dir, '')
    result = tfm.ls()
    self.assertIsNone(result)
