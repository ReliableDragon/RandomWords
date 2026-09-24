import os
import tempfile
import unittest
from pathlib import Path

from vault import RevisionConflict, VaultManager
from world_backlog import IdeaSpanMismatch, list_ideas, strike_idea


class WorldBacklogTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.root = os.path.join(self.temp.name, 'vault')
    self.recovery = os.path.join(self.temp.name, 'recovery')
    os.mkdir(self.root)
    os.mkdir(os.path.join(self.root, 'Ideas'))
    self.vault = VaultManager(self.root, self.recovery)

  def tearDown(self):
    self.temp.cleanup()

  def write_note(self, text):
    path = os.path.join(self.root, 'Ideas', 'Ideas.md')
    with open(path, 'wb') as note:
      note.write(text.encode('utf-8'))
    return 'Ideas/Ideas.md', path

  def test_lists_direct_markdown_bullets_with_utf16_spans_and_done_state(self):
    source = '# Backlog\r\n* 😀 echo\r\n- echo\r\n+ ~~finished idea~~  \r\n'
    path, full = self.write_note(source)
    rows = list_ideas(self.vault)
    self.assertEqual([row['expected'] for row in rows], ['😀 echo', 'echo', 'finished idea'])
    self.assertEqual([row['done'] for row in rows], [False, False, True])
    self.assertEqual([row['path'] for row in rows], [path] * 3)
    for row in rows:
      encoded = source.encode('utf-16-le')
      start = row['start'] * 2
      end = row['end'] * 2
      self.assertEqual(encoded[start:end].decode('utf-16-le'), row['expected'])
    self.assertEqual(Path(full).read_bytes(), source.encode('utf-8'))

  def test_strike_uses_exact_utf16_span_and_preserves_crlf_and_duplicates(self):
    source = '* 😀 echo\r\n- echo\r\n- echo\r\n'
    path, full = self.write_note(source)
    rows = list_ideas(self.vault)
    result = strike_idea(self.vault, path, rows[0]['revision'], rows[0]['start'],
                         rows[0]['end'], rows[0]['expected'])
    self.assertTrue(result['revision'])
    updated = Path(full).read_bytes()
    self.assertEqual(updated, '* ~~😀 echo~~\r\n- echo\r\n- echo\r\n'.encode())
    remaining = list_ideas(self.vault)
    self.assertEqual([row['expected'] for row in remaining], ['😀 echo', 'echo', 'echo'])
    self.assertEqual([row['done'] for row in remaining], [True, False, False])
    self.assertNotEqual(remaining[1]['start'], remaining[2]['start'])

  def test_stale_revision_raises_conflict_without_touching_source(self):
    path, full = self.write_note('* initial\r\n')
    row = list_ideas(self.vault)[0]
    self.vault.write(path, '* external\r\n', row['revision'])
    before = Path(full).read_bytes()
    with self.assertRaises(RevisionConflict):
      strike_idea(self.vault, path, row['revision'], row['start'], row['end'], row['expected'])
    self.assertEqual(Path(full).read_bytes(), before)

  def test_span_mismatch_raises_without_touching_source(self):
    path, full = self.write_note('* duplicate\r\n- duplicate\r\n')
    row = list_ideas(self.vault)[1]
    before = Path(full).read_bytes()
    with self.assertRaises(IdeaSpanMismatch):
      strike_idea(self.vault, path, row['revision'], row['start'], row['end'], 'different')
    self.assertEqual(Path(full).read_bytes(), before)

  def test_strike_rejects_exact_nonbullet_text_and_completed_ideas(self):
    source = '# Ideas\nThis is not a bullet.\n* ~~already finished~~\n'
    path, full = self.write_note(source)
    rows = list_ideas(self.vault)
    done = rows[0]
    before = Path(full).read_bytes()
    with self.assertRaises(IdeaSpanMismatch):
      start = len('# Ideas\n')
      expected = 'This is not a bullet.'
      strike_idea(self.vault, path, done['revision'], start, start + len(expected),
                  expected)
    with self.assertRaises(IdeaSpanMismatch):
      strike_idea(self.vault, path, done['revision'], done['start'], done['end'],
                  done['expected'])
    self.assertEqual(Path(full).read_bytes(), before)


if __name__ == '__main__':
  unittest.main()
