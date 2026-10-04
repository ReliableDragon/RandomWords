import test from 'node:test';
import assert from 'node:assert/strict';

import { asideRanges, findTag, nextRange, todoItems } from '../static/world/entry_todo.js';

test('a plain, finished entry has nothing on its to-do strip', () => {
  assert.deepEqual(todoItems({ tags: ['plant'], notes: [], words: 120, stub: false }, [{ status: 'resolved' }]), []);
  assert.deepEqual(todoItems(null, []), []);
  assert.deepEqual(todoItems({}, undefined), []);
});

test('each applicable item appears, in a fixed order, with plain labels', () => {
  const items = todoItems(
    { tags: ['Plant', 'REWORK'], notes: ['a', 'b', 'c'], words: 12, stub: true },
    [{ status: 'unresolved' }, { status: 'resolved' }, { status: 'ambiguous' }, { status: 'unresolved' }]);
  assert.deepEqual(items.map((item) => [item.kind, item.label]), [
    ['rework', '#rework'],
    ['notes', '3 notes to self'],
    ['stub', 'Stub, 12 words'],
    ['unresolved', '2 unresolved links'],
    ['ambiguous', '1 ambiguous link'],
  ]);
  assert.deepEqual(items.map((item) => item.action), ['tag', 'aside', null, 'links', 'links']);
});

test('singular labels and a stub without a word count', () => {
  const [note] = todoItems({ notes: ['x'] }, []);
  assert.equal(note.label, '1 note to self');
  const [stub] = todoItems({ stub: true }, []);
  assert.equal(stub.label, 'Stub');
  assert.equal(todoItems({ stub: true, words: 1 }, [])[0].label, 'Stub, 1 word');
});

test('only a server-flagged stub counts and #rework must be a whole tag', () => {
  assert.deepEqual(todoItems({ stub: false, words: 3, tags: ['reworked', 'rework-later'] }, []), []);
});

test('asides are found in order with their offsets, and a caret finds the next one', () => {
  const text = 'a ${one} b\n${two} c ${three}';
  const ranges = asideRanges(text);
  assert.equal(ranges.length, 3);
  assert.equal(text.slice(ranges[0].start, ranges[0].end), '${one}');
  assert.equal(text.slice(ranges[2].start, ranges[2].end), '${three}');
  assert.equal(nextRange(ranges, 0), ranges[0]);
  assert.equal(nextRange(ranges, ranges[0].start), ranges[1], 'standing on one moves to the next');
  assert.equal(nextRange(ranges, ranges[0].end), ranges[1]);
  assert.equal(nextRange(ranges, ranges[2].start), ranges[0], 'wraps round after the last');
  assert.equal(nextRange([], 4), null);
  assert.deepEqual(asideRanges(''), []);
  assert.deepEqual(asideRanges(null), []);
});

test('findTag locates a whole #tag and not a longer one or a heading', () => {
  const text = 'Origin: x\n\n#reworked #plant #rework later';
  const found = findTag(text, 'rework');
  assert.equal(text.slice(found.start, found.end), '#rework');
  assert.equal(found.start, text.indexOf('#rework later'));
  assert.equal(findTag('#REWORK', 'rework').start, 0);
  assert.equal(findTag('no tags here', 'rework'), null);
  assert.equal(findTag('see C#rework', 'rework'), null);
  assert.equal(findTag('', 'rework'), null);
});
