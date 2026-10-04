import test from 'node:test';
import assert from 'node:assert/strict';

import { matchingIdeas } from '../static/world/idea.js';
import { lexiconQuery } from '../static/world/lexicon.js';
import { normalizeSections } from '../static/world/upkeep.js';
import { parseReference } from '../static/world/refcard.js';
import { emit, Events, on } from '../static/world/events.js';

test('upkeep sections may be an object keyed by name', () => {
  const data = { sections: { stubs: [{ path: 'A.md' }], spelling_drift: { items: [{ from: 'a', to: 'b' }] }, empty: null } };
  assert.deepEqual(normalizeSections(data), [
    ['stubs', [{ path: 'A.md' }]], ['spelling_drift', [{ from: 'a', to: 'b' }]], ['empty', []],
  ]);
});

test('upkeep sections may be a list of keyed sections', () => {
  const data = { sections: [{ key: 'stubs', items: [1] }, { title: 'Links', entries: [2] }, {}] };
  assert.deepEqual(normalizeSections(data), [['stubs', [1]], ['Links', [2]], ['Findings', []]]);
  assert.deepEqual(normalizeSections({}), []);
});

test('the lexicon query includes only the filters that are set', () => {
  assert.deepEqual(lexiconQuery({ q: '', biome: '', once: false }), {});
  assert.deepEqual(lexiconQuery({ q: 'loam', biome: 'Biomes/Marsh.md', once: true }), {
    q: 'loam', biome: 'Biomes/Marsh.md', once: '1',
  });
});

test('a retry only matches the same open idea in the same file', () => {
  const prior = { path: 'Ideas.md', expected: 'A drowned bell' };
  const ideas = [
    { path: 'Ideas.md', expected: 'A drowned bell', done: false },
    { path: 'Ideas.md', expected: 'A drowned bell', done: true },
    { path: 'Other.md', expected: 'A drowned bell', done: false },
    { path: 'Ideas.md', expected: 'Something else', done: false },
  ];
  assert.deepEqual(matchingIdeas(ideas, prior), [ideas[0]]);
  assert.deepEqual(matchingIdeas(undefined, prior), []);
});

test('the reference card picks out header, first paragraph, facts and quotes', () => {
  const raw = [
    '---', 'title: Ada', '---', 'From: [[Harbor]]', 'Themes: loss', '',
    'Ada keeps the light.', 'She never sleeps.', '', 'More prose.', '',
    '## Facts', '- Born in spring', '- Left-handed', '## Notes', 'Not a fact.', '',
    '> "The tide remembers."', '> - [[Ada]]', '', 'Loose line - [[Ada]]',
  ].join('\r\n');
  const parts = parseReference(raw);
  assert.equal(parts.header, '---\ntitle: Ada\n---\nFrom: [[Harbor]]\nThemes: loss');
  assert.equal(parts.first, 'Ada keeps the light.\nShe never sleeps.');
  assert.equal(parts.facts, '## Facts\n- Born in spring\n- Left-handed');
  assert.equal(parts.quotes, '> "The tide remembers."\n> - [[Ada]]\n\nLoose line - [[Ada]]');
});

test('an entry with no header still yields a first paragraph', () => {
  assert.deepEqual(parseReference('Just prose.\n\nSecond.'), { header: '', first: 'Just prose.', facts: '', quotes: '' });
  assert.deepEqual(parseReference(undefined), { header: '', first: '', facts: '', quotes: '' });
});

test('events reach every listener, and one failing listener does not stop the rest', () => {
  const seen = [];
  const off = on(Events.KEPT_CHANGED, () => { throw new Error('listener bug'); });
  const offSecond = on(Events.KEPT_CHANGED, (detail) => seen.push(detail));
  const originalError = console.error;
  console.error = () => {};
  try {
    emit(Events.KEPT_CHANGED, 1);
    off();
    emit(Events.KEPT_CHANGED, 2);
  } finally {
    console.error = originalError;
    offSecond();
  }
  assert.deepEqual(seen, [1, 2]);
  emit(Events.KEPT_CHANGED, 3);
  assert.deepEqual(seen, [1, 2]);
});
