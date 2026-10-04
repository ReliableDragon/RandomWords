import test from 'node:test';
import assert from 'node:assert/strict';

import {
  addRecent, clearSummary, clip, draftRows, dropRecent, relativeTime, worthALook,
} from '../static/world/welcome.js';

const item = (path, opened) => ({ path, title: path.replace(/\.md$/, ''), opened });

test('the recent list puts the newest first, never repeats an entry and stops at the cap', () => {
  let list = [];
  ['a.md', 'b.md', 'c.md'].forEach((path) => { list = addRecent(list, item(path), 8); });
  assert.deepEqual(list.map((x) => x.path), ['c.md', 'b.md', 'a.md']);
  list = addRecent(list, item('a.md', 'later'), 8);
  assert.deepEqual(list.map((x) => x.path), ['a.md', 'c.md', 'b.md']);
  assert.equal(list[0].opened, 'later');
  for (let i = 0; i < 12; i++) list = addRecent(list, item('n' + i + '.md'), 8);
  assert.equal(list.length, 8);
  assert.equal(list[0].path, 'n11.md');
  assert.deepEqual(addRecent(null, item('x.md')).map((x) => x.path), ['x.md']);
});

test('dropRecent removes one entry and tolerates a missing list', () => {
  assert.deepEqual(dropRecent([item('a.md'), item('b.md')], 'a.md').map((x) => x.path), ['b.md']);
  assert.deepEqual(dropRecent(undefined, 'a.md'), []);
});

test('relativeTime speaks in days and falls back to a date', () => {
  const now = new Date(2026, 8, 30, 15, 0).getTime();
  assert.equal(relativeTime(new Date(2026, 8, 30, 1, 0).toISOString(), now), 'today');
  assert.equal(relativeTime(new Date(2026, 8, 29, 23, 0).toISOString(), now), 'yesterday');
  assert.equal(relativeTime(new Date(2026, 8, 27, 9, 0).toISOString(), now), '3 days ago');
  assert.match(relativeTime(new Date(2026, 7, 1, 9, 0).toISOString(), now), /\S/);
  assert.equal(relativeTime('nonsense', now), '');
  assert.equal(relativeTime(undefined, now), '');
});

test('both kinds of draft share one list, newest first, with plain titles', () => {
  const rows = draftRows(
    [{ id: 'n1', title: '  ', updated: '2026-09-30T10:00:00.000Z' }, { id: 'n2', title: 'Marsh Wren', updated: '2026-09-29T10:00:00.000Z' }],
    [{ path: 'People/Ada.md', text: 'x', updated: '2026-09-30T11:00:00.000Z' }, { path: 'Root.md', text: 'y' }]);
  assert.deepEqual(rows.map((row) => [row.kind, row.key, row.title]), [
    ['entry', 'People/Ada.md', 'Ada'],
    ['new', 'n1', 'Untitled entry'],
    ['new', 'n2', 'Marsh Wren'],
    ['entry', 'Root.md', 'Root'],
  ]);
  assert.match(rows[0].detail, /People/);
  assert.match(rows[3].detail, /vault root/);
  assert.deepEqual(draftRows(null, undefined), []);
});

const SECTIONS = {
  unresolved_links: [{ path: 'A.md', title: 'A', target: 'Zed' }, { path: 'B.md', title: 'B', target: 'Yak' }],
  notes_to_self: [{ path: 'C.md', title: 'C', text: ' Rewrite. ' }],
  rework: [{ path: 'D.md', title: 'D' }],
  stubs: [{ path: 'E.md', title: 'E', words: 3 }],
};

test('worth a look takes three items of different kinds, most useful first', () => {
  const found = worthALook(SECTIONS, 0);
  assert.deepEqual(found.map((x) => x.kind), ['unresolved_links', 'notes_to_self', 'rework']);
  assert.match(found[0].text, /"Zed".*A/);
  assert.match(found[1].text, /"Rewrite\."/);
  assert.equal(found[0].path, 'A.md');
});

test('the seed moves which item of a kind is offered', () => {
  assert.equal(worthALook(SECTIONS, 1)[0].path, 'B.md');
  assert.equal(worthALook(SECTIONS, 2)[0].path, 'A.md');
});

test('worth a look skips empty or missing sections and honours the limit', () => {
  assert.deepEqual(worthALook({ stubs: [{ path: 'E.md', title: 'E', words: 3 }] }, 5).map((x) => x.kind), ['stubs']);
  assert.deepEqual(worthALook({}, 0), []);
  assert.deepEqual(worthALook(undefined, 0), []);
  assert.equal(worthALook(SECTIONS, 0, 1).length, 1);
});

test('the clear confirmation counts drafts and says when the open draft is included', () => {
  const plain = clearSummary({ drafts: 1, newDrafts: 1 }, null);
  assert.match(plain, /2 unsaved drafts/);
  assert.match(plain, /Nothing in your vault changes/);
  assert.doesNotMatch(plain, /open in the editor/);
  assert.match(clearSummary({ drafts: 0, newDrafts: 1 }, null), /1 unsaved draft /);
  const open = clearSummary({ drafts: 2, newDrafts: 0 }, 'Marsh Wren');
  assert.match(open, /open in the editor, "Marsh Wren"/);
  assert.match(open, /no longer kept on this device until you change it again/);
});

test('a long note to self is clipped on one line and a short one is untouched', () => {
  assert.equal(clip('short  note\nhere', 90), 'short note here');
  const long = clip('word '.repeat(60), 40);
  assert.equal(long.length, 40);
  assert.ok(long.endsWith('…'));
  assert.equal(clip(null, 5), '');
  const found = worthALook({ notes_to_self: [{ path: 'C.md', title: 'C', text: 'x'.repeat(500) }] }, 0);
  assert.ok(found[0].text.length < 140);
});
