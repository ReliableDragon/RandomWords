import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

// Timers must not keep the test process alive (the editor polls every 12s).
const realSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };
globalThis.setInterval = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setInterval);

const search = await import('../static/world/search.js');
const { state } = await import('../static/world/state.js');

const settle = (ms) => new Promise((resolve) => realSetTimeout(resolve, ms || 0));

test('snippetParts finds the marked match, falling back when offsets are wrong', () => {
  const row = { snippet: 'a quiet Reservoir here', snippet_match: [8, 17] };
  assert.deepEqual(search.snippetParts(row, 'reservoir'), { before: 'a quiet ', match: 'Reservoir', after: ' here' });
  const bad = { snippet: 'a quiet Reservoir here', snippet_match: [0, 3] };
  assert.equal(search.snippetParts(bad, 'reservoir').match, 'Reservoir');
  assert.equal(search.snippetParts({}, 'x'), null);
});

test('duplicateTitles and countMessage', () => {
  assert.deepEqual(Array.from(search.duplicateTitles([{ title: 'Wickrill' }, { title: 'wickrill' }, { title: 'Fen' }])), ['wickrill']);
  assert.equal(search.countMessage(0, 0), 'No matches.');
  assert.equal(search.countMessage(1, 1), '1 result.');
  assert.equal(search.countMessage(45, 30), '30 of 45 results shown.');
});

test('matchedAlias trusts the server and can work it out for older replies', () => {
  assert.equal(search.matchedAlias({ match: 'alias', matched_alias: 'Niuri' }, 'niu'), 'Niuri');
  assert.equal(search.matchedAlias({ match: 'title', title: 'Niuri River', aliases: ['Niuri'] }, 'niuri'), null);
  assert.equal(search.matchedAlias({ title: 'Niuri River & Delta', aliases: ['Delta Run'] }, 'run'), 'Delta Run');
});

const RESULTS = [
  { path: 'A/Wickrill.md', title: 'Wickrill', folder: 'A', kind: 'Flora and Fauna', words: 391, stub: false, match: 'title' },
  { path: 'B/Wickrill.md', title: 'Wickrill', folder: 'B', kind: 'Othernatural', words: 1, stub: true, match: 'title' },
  { path: 'C/Niuri.md', title: 'Niuri River', folder: 'C', kind: 'Locations', words: 28, match: 'alias', matched_alias: 'Wick' },
  { path: 'D/Reed.md', title: 'Reed', folder: 'D', match: 'text', snippet: 'near the wickrill pools', snippet_match: [9, 13] },
];

test('results show kind, words, stub, alias and snippet; arrow keys and Enter work; the count is announced', async () => {
  const dom = installFakeDom();
  const $ = (id) => dom.document.getElementById(id);
  const calls = installFakeFetch({
    'GET /api/world/search': () => ({ body: { ok: true, data: { results: RESULTS } } }),
    'GET /api/world/entry': () => ({ body: { ok: true, data: { path: 'B/Wickrill.md', text: 'x', entry: { title: 'Wickrill' } } } }),
    'GET /api/world/tree': () => ({ body: { ok: true, data: { entries: [] } } }),
    'POST /api/world/nearby': () => ({ body: { ok: true, data: { groups: {} } } }),
  });
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {}, length: 0, key: () => null };
  try {
    state.current = null;
    search.initSearch();
    const input = $('worldSearch');
    input.value = 'wick';
    input.dispatch('input');
    await settle(260);
    assert.equal(calls.filter((c) => c.path === '/api/world/search').length, 1);
    const rows = findAll($('searchResults'), (n) => n.classList.contains('search-result'));
    assert.equal(rows.length, 4);
    assert.equal($('searchResults').hidden, false);
    assert.equal($('searchStatus').textContent, '4 results.');
    assert.match(rows[0].textContent, /Wickrill.*Flora and Fauna.*391 words/);
    assert.match(rows[1].textContent, /stub/);
    assert.match(rows[2].textContent, /alias of Wick/);
    const mark = findAll(rows[3], (n) => n.tagName === 'mark')[0];
    assert.equal(mark.textContent, 'wick');
    // Same-title entries are told apart by their folder.
    const folders = findAll(rows[0], (n) => n.classList.contains('search-result-folder'));
    assert.equal(folders[0].classList.contains('is-duplicate'), true);
    assert.equal(findAll(rows[3], (n) => n.classList.contains('is-duplicate')).length, 0);

    let focused = null;
    rows.forEach((row) => { row.focus = () => { focused = row; }; });
    input.dispatch('keydown', { key: 'ArrowDown' });
    assert.equal(focused, rows[0]);
    rows[0].dispatch('keydown', { key: 'ArrowDown' });
    assert.equal(focused, rows[1]);
    rows[1].dispatch('keydown', { key: 'End' });
    assert.equal(focused, rows[3]);
    input.focus = () => { focused = input; };
    rows[0].dispatch('keydown', { key: 'ArrowUp' });
    assert.equal(focused, input);
    rows[1].dispatch('keydown', { key: 'Escape' });
    assert.equal($('searchResults').hidden, true);

    input.dispatch('input');
    await settle(260);
    input.dispatch('keydown', { key: 'Enter' });
    await settle(20);
    assert.equal(calls.some((c) => c.path === '/api/world/entry' && /A%2FWickrill/.test(c.url)), true);
    assert.equal(input.value, '');
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
  }
});
