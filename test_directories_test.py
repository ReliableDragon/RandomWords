import os
import unittest

from test_directories import TestDirectories

class TestDirectoriesTest(unittest.TestCase):
  
  def test_context(self):
    with TestDirectories() as  td:
      self.assertTrue(os.path.exists(td.d1.name))
      self.assertFalse(os.path.isfile(td.d1.name))
      self.assertTrue(os.path.exists(td.d2.name))
      self.assertFalse(os.path.isfile(td.d2.name))
      self.assertTrue(os.path.exists(td.d3.name))
      self.assertFalse(os.path.isfile(td.d3.name))

      self.assertTrue(os.path.exists(td.tf1.name))
      self.assertTrue(os.path.isfile(td.tf1.name))
      self.assertTrue(os.path.exists(td.tf2.name))
      self.assertTrue(os.path.exists(td.tf2.name))
      self.assertTrue(os.path.exists(td.tf3.name))
      self.assertTrue(os.path.isfile(td.tf3.name))
      self.assertTrue(os.path.isfile(td.tf4.name))
      self.assertTrue(os.path.isfile(td.tf4.name))

      self.assertTrue(os.path.exists(td.ntf1.name))
      self.assertTrue(os.path.exists(td.ntf1.name))
      self.assertTrue(os.path.isfile(td.ntf2.name))
      self.assertTrue(os.path.isfile(td.ntf2.name))

      with open(td.tf3.name) as f:
        self.assertEqual(f.read(), 'robophicles aeschylinux euripiDOS')


    self.assertFalse(os.path.exists(td.d1.name))
    self.assertFalse(os.path.exists(td.d2.name))
    self.assertFalse(os.path.exists(td.d3.name))

    self.assertFalse(os.path.exists(td.tf1.name))
    self.assertFalse(os.path.exists(td.tf2.name))
    self.assertFalse(os.path.exists(td.tf3.name))
    self.assertFalse(os.path.exists(td.tf4.name))

    self.assertFalse(os.path.exists(td.ntf1.name))
    self.assertFalse(os.path.exists(td.ntf2.name))
