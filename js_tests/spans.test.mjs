import test from 'node:test';
import assert from 'node:assert/strict';

import { replaceSpan, spanIsCurrent } from '../static/world/spans.js';

const text = 'The rainseed lantern and the raiseed lamp.';
const start = text.indexOf('raiseed');
const span = { revision: 'r1', start, end: start + 7, expected: 'raiseed' };

test('a span is current when revision and text still match', () => {
  assert.equal(text.slice(span.start, span.end), 'raiseed');
  assert.equal(spanIsCurrent({ revision: 'r1', text }, span), true);
});

test('a span is stale when the entry has a new revision', () => {
  assert.equal(spanIsCurrent({ revision: 'r2', text }, span), false);
});

test('a span is stale when the characters at the offsets changed', () => {
  assert.equal(spanIsCurrent({ revision: 'r1', text: 'X' + text }, span), false);
  assert.equal(spanIsCurrent({ revision: 'r1', text: text.replace('raiseed', 'raiseeD') }, span), false);
});

test('a span past the end of the text is stale', () => {
  assert.equal(spanIsCurrent({ revision: 'r1', text: 'short' }, span), false);
});

test('replaceSpan swaps exactly the span and leaves the rest', () => {
  assert.equal(replaceSpan(text, span.start, span.end, 'rainseed'), 'The rainseed lantern and the rainseed lamp.');
  assert.equal(replaceSpan('abc', 1, 1, 'X'), 'aXbc');
  assert.equal(replaceSpan('abc', 0, 3, ''), '');
});

test('offsets are UTF-16 code units, matching the browser textarea', () => {
  const emoji = '\u{1F327} rain raiseed';
  const at = emoji.indexOf('raiseed');
  assert.equal(at, 2 + 1 + 4 + 1, 'the emoji takes two code units');
  assert.equal(
    spanIsCurrent({ revision: 'r', text: emoji }, { revision: 'r', start: at, end: at + 7, expected: 'raiseed' }),
    true);
});
