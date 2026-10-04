import test from 'node:test';
import assert from 'node:assert/strict';

import {
  completionText, parseTrigger, prioritizeNearby, tagCompletions,
} from '../static/world/autocomplete.js';

test('[[ starts a link completion with the query after it', () => {
  const text = 'She walked to [[Har';
  assert.deepEqual(parseTrigger(text), { token: 'link', marker: 14, start: 16, query: 'Har' });
});

test('an empty query right after [[ is still a link trigger', () => {
  assert.deepEqual(parseTrigger('see [['), { token: 'link', marker: 4, start: 6, query: '' });
});

test('# starts a tag completion', () => {
  assert.deepEqual(parseTrigger('Tags: #flo'), { token: 'tag', marker: 6, start: 7, query: 'flo' });
});

test('a closed link or a newline ends the trigger', () => {
  assert.equal(parseTrigger('done [[Harbor]] and'), null);
  assert.equal(parseTrigger('[[Har\nbor'), null);
  assert.equal(parseTrigger('plain text'), null);
});

test('the query stops at a second # or a bracket', () => {
  assert.deepEqual(parseTrigger('[[a#b'), { token: 'tag', marker: 3, start: 4, query: 'b' });
  assert.equal(parseTrigger('#a]'), null);
});

test('the marker is the nearest opening [[', () => {
  const trigger = parseTrigger('[[One]] and [[Tw');
  assert.equal(trigger.marker, 12);
  assert.equal(trigger.query, 'Tw');
});

test('tag completions accept strings and objects, add the # and filter by prefix', () => {
  const response = { tags: ['flora', '#fauna', { tag: 'floral' }, { name: 'loaming' }, ''] };
  assert.deepEqual(tagCompletions(response, 'flo'), [
    { title: '#flora', path: '' }, { title: '#floral', path: '' },
  ]);
  assert.deepEqual(tagCompletions(['flora', 'Fauna'], 'F').map((t) => t.title), ['#flora', '#Fauna']);
});

test('tag completions are capped at ten', () => {
  const tags = Array.from({ length: 20 }, (_, i) => 't' + i);
  assert.equal(tagCompletions({ tags }, 't').length, 10);
});

test('entries Nearby already suggests sort first, otherwise order is kept', () => {
  const results = [{ path: 'a.md' }, { path: 'b.md' }, { path: 'c.md' }, { path: 'd.md' }];
  assert.deepEqual(prioritizeNearby(results, ['c.md', 'b.md']).map((r) => r.path), ['b.md', 'c.md', 'a.md', 'd.md']);
  assert.deepEqual(results.map((r) => r.path), ['a.md', 'b.md', 'c.md', 'd.md'], 'input is not mutated');
});

test('a plain title completes to a bare wikilink', () => {
  const item = { title: 'Harbor', path: 'Places/Harbor.md' };
  assert.equal(completionText({ token: 'link', query: 'Har' }, item, [item]), '[[Harbor]]');
});

test('a tag completes to its own text', () => {
  assert.equal(completionText({ token: 'tag', query: 'fl' }, { title: '#flora' }, []), '#flora');
});

test('a shared title completes to the full path', () => {
  const a = { title: 'Harbor', path: 'Places/Harbor.md' };
  const b = { title: 'harbor', path: 'People/Harbor.md' };
  assert.equal(completionText({ token: 'link', query: 'har' }, a, [a, b]), '[[Places/Harbor]]');
  const noPath = { title: 'Harbor', folder: 'Places' };
  assert.equal(completionText({ token: 'link', query: 'har' }, noPath, [noPath, b]), '[[Places/Harbor]]');
});

test('an alias the writer was typing is kept as the label', () => {
  const item = { title: 'Harbor', path: 'Places/Harbor.md', aliases: ['Port', 'the docks'] };
  assert.equal(completionText({ token: 'link', query: 'po' }, item, [item]), '[[Harbor|Port]]');
  assert.equal(completionText({ token: 'link', query: 'har' }, item, [item]), '[[Harbor]]');
});

import { capturesKey, moveHighlight, nearbyItems } from '../static/world/autocomplete.js';

test('a bare [[ lists Nearby merged cards in ranked order', () => {
  const nearby = { merged: [
    { path: 'A.md', title: 'A', folder: 'F', reasons: [] }, { path: 'B.md', title: 'B' }, { title: 'no path' },
  ] };
  assert.deepEqual(nearbyItems(nearby), [
    { path: 'A.md', title: 'A', folder: 'F' }, { path: 'B.md', title: 'B', folder: undefined },
  ]);
  assert.deepEqual(nearbyItems(nearby, 1).length, 1);
  assert.deepEqual(nearbyItems(null), []);
  assert.deepEqual(nearbyItems({ groups: {} }), []);
});

test('arrow keys move the highlight, starting from nothing', () => {
  assert.equal(moveHighlight(-1, 3, 'ArrowDown'), 0);
  assert.equal(moveHighlight(-1, 3, 'ArrowUp'), 2);
  assert.equal(moveHighlight(2, 3, 'ArrowDown'), 0);
  assert.equal(moveHighlight(0, 3, 'ArrowUp'), 2);
  assert.equal(moveHighlight(0, 0, 'ArrowDown'), -1);
});

test('Enter and Tab are taken only while an option is highlighted', () => {
  assert.equal(capturesKey('Enter', true, 0), true);
  assert.equal(capturesKey('Tab', true, 2), true);
  assert.equal(capturesKey('Enter', true, -1), false);
  assert.equal(capturesKey('Enter', false, 0), false);
  assert.equal(capturesKey('a', true, 0), false);
});
