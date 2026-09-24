import os
import tempfile
import unittest

from vault import DestinationConflict, InvalidPath, RevisionConflict, VaultManager


class VaultManagerTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.root = os.path.join(self.temp.name, 'vault')
    self.recovery = os.path.join(self.temp.name, 'recovery')
    os.mkdir(self.root)
    self.vault = VaultManager(self.root, self.recovery)

  def tearDown(self):
    self.temp.cleanup()

  def test_path_validation_and_outside_symlink(self):
    for path in ('../escape.md', '/tmp/escape.md', '.obsidian/app.md', 'folder/.git/x.md', 'a/./b.md', 'a\\b.md', 'bad\x00name.md'):
      with self.subTest(path=path), self.assertRaises(InvalidPath):
        self.vault.resolve(path)
    with self.assertRaises(InvalidPath):
      self.vault.read('read.txt')
    outside = os.path.join(self.temp.name, 'outside')
    os.mkdir(outside)
    os.symlink(outside, os.path.join(self.root, 'linked'))
    with self.assertRaises(InvalidPath):
      self.vault.resolve('linked/secret.md')

  def test_read_hashes_exact_bytes_and_lists_markdown(self):
    os.mkdir(os.path.join(self.root, 'Folder'))
    path = os.path.join(self.root, 'Folder', 'Café.md')
    with open(path, 'wb') as f:
      f.write(b'\xef\xbb\xbfhello\r\n')
    text, revision = self.vault.read('Folder/Café.md')
    self.assertEqual(text, '\ufeffhello\r\n')
    self.assertTrue(revision.startswith('sha256:'))
    self.assertEqual(self.vault.ls(), ['Folder'])
    self.assertEqual(self.vault.ls('Folder'), ['Folder/Café.md'])
    self.assertIn('Folder/Café.md', self.vault.stat_all())

  def test_revision_conflict_and_version_bound_replacement(self):
    os.makedirs(os.path.join(self.root, 'notes'))
    target = os.path.join(self.root, 'notes', 'one.md')
    with open(target, 'wb') as f:
      f.write(b'initial')
    _, old_revision = self.vault.read('notes/one.md')
    with open(target, 'wb') as f:
      f.write(b'external edit')
    with self.assertRaises(RevisionConflict) as caught:
      self.vault.write('notes/one.md', 'my edit', old_revision)
    conflict = caught.exception
    self.assertEqual(conflict.current_text, 'external edit')
    result = self.vault.write('notes/one.md', 'my edit', old_revision,
                              replace_revision=conflict.current_revision)
    self.assertEqual(result['revision'], self.vault.read('notes/one.md')[1])
    with open(result['recovery_path'], 'rb') as f:
      self.assertEqual(f.read(), b'external edit')
    with self.assertRaises(RevisionConflict):
      self.vault.write('notes/one.md', 'stale again', old_revision,
                       replace_revision=conflict.current_revision)

  def test_create_is_exclusive_and_checks_normalized_casefold_collision(self):
    first = self.vault.create('Café.md', 'one')
    self.assertTrue(first['revision'].startswith('sha256:'))
    self.assertEqual(os.listdir(self.root), ['Café.md'])
    with self.assertRaises(DestinationConflict):
      self.vault.create('CAFÉ.md', 'two')
    with self.assertRaises(DestinationConflict):
      self.vault.create('Cafe\u0301.md', 'three')

  def test_write_preserves_bom_newline_and_final_newline_conventions(self):
    samples = [
        (b'\xef\xbb\xbfold\r\nline\r\n', '\ufeffnew\ntext\n',
         b'\xef\xbb\xbfnew\r\ntext\r\n'),
        (b'old\nline', 'new\r\ntext\r\n', b'new\ntext'),
    ]
    for index, (original, edited, expected) in enumerate(samples):
      path = f'note-{index}.md'
      full = os.path.join(self.root, path)
      with open(full, 'wb') as f:
        f.write(original)
      _, revision = self.vault.read(path)
      self.vault.write(path, edited, revision)
      with open(full, 'rb') as f:
        self.assertEqual(f.read(), expected)

  def test_unchanged_text_keeps_multiple_trailing_blank_lines_byte_for_byte(self):
    original = b'\xef\xbb\xbfHeading\r\n\r\n\r\n'
    path = 'many-lines.md'
    full = os.path.join(self.root, path)
    with open(full, 'wb') as f:
      f.write(original)
    text, revision = self.vault.read(path)
    browser_text = text.replace('\r\n', '\n')
    self.vault.write(path, browser_text, revision)
    with open(full, 'rb') as f:
      self.assertEqual(f.read(), original)

  def test_edited_text_retains_trailing_blank_lines(self):
    path = 'trailing.md'
    full = os.path.join(self.root, path)
    with open(full, 'wb') as f:
      f.write(b'old\r\n\r\n\r\n')
    _, revision = self.vault.read(path)
    self.vault.write(path, 'new\n\n\n', revision)
    with open(full, 'rb') as f:
      self.assertEqual(f.read(), b'new\r\n\r\n\r\n')

  def test_recovery_names_distinguish_paths_that_sanitize_the_same(self):
    paths = ('a/b__c.md', 'a__b/c.md')
    for path in paths:
      full = os.path.join(self.root, path)
      os.makedirs(os.path.dirname(full), exist_ok=True)
      with open(full, 'wb') as f:
        f.write(b'old')
      _, revision = self.vault.read(path)
      with open(full, 'wb') as f:
        f.write(b'external')
      conflict = None
      try:
        self.vault.write(path, 'new', revision)
      except RevisionConflict as error:
        conflict = error
      self.assertIsNotNone(conflict)
      result = self.vault.write(path, 'new', revision,
                                replace_revision=conflict.current_revision)
      self.assertTrue(os.path.isfile(result['recovery_path']))
    self.assertEqual(len(os.listdir(self.recovery)), 2)


if __name__ == '__main__':
  unittest.main()
