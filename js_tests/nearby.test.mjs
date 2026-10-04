import test from 'node:test';
import assert from 'node:assert/strict';

import { canApplySuggestion, nearbyLink, suggestionLink } from '../static/world/nearby.js';

const text = 'Ada met the loam-keeper at dusk.';
const suggestion = {
  title: 'Loam-keeper', path: 'People/Loam-keeper.md', start: 12, end: 23,
  expected: 'loam-keeper', client_revision: '17-3',
};

test('Link match applies when the draft, revision and span are unchanged', () => {
  assert.equal(text.slice(12, 23), 'loam-keeper');
  assert.equal(canApplySuggestion(suggestion, '17-3', text, text), true);
});

test('Link match is refused when the response belongs to another request', () => {
  assert.equal(canApplySuggestion(suggestion, '17-4', text, text), false);
});

test('a suggestion without its own revision is judged by the request revision', () => {
  const bare = Object.assign({}, suggestion, { client_revision: undefined });
  assert.equal(canApplySuggestion(bare, '17-3', text, text), true);
});

test('Link match is refused after any edit to the draft', () => {
  assert.equal(canApplySuggestion(suggestion, '17-3', text, 'X' + text), false);
  assert.equal(canApplySuggestion(suggestion, '17-3', text, text + ' More.'), false);
});

test('Link match is refused when the span no longer holds the expected text', () => {
  const moved = Object.assign({}, suggestion, { start: 13, end: 24 });
  assert.equal(canApplySuggestion(moved, '17-3', text, text), false);
});

test('the inserted link uses the display text when it differs from the title', () => {
  assert.equal(suggestionLink(suggestion), '[[Loam-keeper|loam-keeper]]');
  assert.equal(
    suggestionLink(Object.assign({}, suggestion, { expected: 'Loam-keeper' })),
    '[[Loam-keeper]]');
});

test('link_target wins over the title and loses its .md suffix', () => {
  const target = Object.assign({}, suggestion, { link_target: 'People/Loam-keeper.md', expected: 'Loam-keeper' });
  assert.equal(suggestionLink(target), '[[People/Loam-keeper|Loam-keeper]]');
});

test('Insert link writes the path as target and the title as label', () => {
  assert.equal(nearbyLink({ title: 'Loam-keeper', path: 'People/Loam-keeper.md' }), '[[People/Loam-keeper|Loam-keeper]]');
  assert.equal(nearbyLink({ title: 'Ada', path: 'Ada.md' }), '[[Ada]]');
});

import { cardOffers, namedReason } from '../static/world/nearby.js';

const merged = {
  path: 'Flora/Glow Fox.md', title: 'Glow Fox', folder: 'Flora', is_place: false, namesake: false,
  reasons: [
    { group: 'same_tags', text: 'Shared tags: bright' },
    { group: 'named_not_linked', text: 'Named as Foxfire', start: 17, end: 24, expected: 'Foxfire',
      client_revision: 'r1', link_target: 'Glow Fox' },
  ],
};

test('a named_not_linked reason becomes a Link match suggestion with the card identity', () => {
  const reason = namedReason(merged);
  assert.equal(reason.title, 'Glow Fox');
  assert.equal(reason.path, 'Flora/Glow Fox.md');
  assert.equal(suggestionLink(reason), '[[Glow Fox|Foxfire]]');
  const text = 'x'.repeat(17) + 'Foxfire' + ' after';
  assert.equal(canApplySuggestion(reason, 'r1', text, text), true);
  assert.equal(canApplySuggestion(reason, 'r1', text, 'y' + text), false);
  assert.equal(namedReason({ path: 'A.md', reasons: [{ group: 'same_tags', text: 'x' }] }), null);
  assert.equal(namedReason({ path: 'A.md' }), null);
});

test('cards offer Link match, Insert link, Use as From and the namesake badge as data says', () => {
  assert.deepEqual(cardOffers(merged), {
    linkMatch: namedReason(merged), insertLink: true, useAsFrom: false, namesake: false,
  });
  const place = { path: 'Locations/Loch.md', title: 'Loch', is_place: true, namesake: true, reasons: [] };
  assert.deepEqual(cardOffers(place), { linkMatch: null, insertLink: true, useAsFrom: true, namesake: true });
});
