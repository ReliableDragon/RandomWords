// Editor hardening: stale drafts, late responses, scroll reveal and sync,
// caches, and small guards. Pure pieces first, then flows on the fake page.

import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

const realSetInterval = globalThis.setInterval;
const realSetTimeout = globalThis.setTimeout;
globalThis.setInterval = (fn, ms) => { const t = realSetInterval(fn, ms); t.unref(); return t; };
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };

const { state } = await import('../static/world/state.js');
const { emit, Events } = await import('../static/world/events.js');
const editor = await import('../static/world/editor.js');
const marks = await import('../static/world/draft_marks.js');
const nearby = await import('../static/world/nearby.js');
const create = await import('../static/world/create.js');
const { storage } = await import('../static/world/storage.js');
const { revealDelta } = await import('../static/world/reveal.js');
const { proportionalScroll } = await import('../static/world/preview_layout.js');
const { draftBase, entryLinkTarget } = await import('../static/world/text.js');
const { buildMarks, findDriftRanges, findWikilinks, problemLinks, linkStatusMap } =
  await import('../static/world/editor_marks.js');

const settle = (ms) => new Promise((resolve) => setTimeout(resolve, ms || 0));
const reply = (data) => ({ body: { ok: true, message: '', data } });
const ENTRY = {
  path: 'People/Ada.md', revision: 'r1', generation: 5, text: 'Ada as she is on disk now.',
  html: '<p>Ada</p>', entry: { title: 'Ada', words: 6 }, links: [], backlinks: [], diagnostics: [],
};
const LEXICON = { generation: 5, entries: [], drift: [] };

// -- Pure pieces ----------------------------------------------------------

test('revealDelta is 0 for a visible span and otherwise brings it a third of the way down', () => {
  assert.equal(revealDelta(100, 130, 0, 600, 8), 0);
  assert.equal(revealDelta(2000, 2030, 0, 600, 8), 1800);
  assert.equal(revealDelta(-500, -470, 0, 600, 8), -700);
  assert.equal(revealDelta(590, 620, 0, 600, 8) > 0, true, 'a span cut off at the bottom scrolls down');
});

test('proportionalScroll keeps panes level and copes with nothing to scroll', () => {
  assert.equal(proportionalScroll(500, 1000, 400), 200);
  assert.equal(proportionalScroll(0, 1000, 400), 0);
  assert.equal(proportionalScroll(5000, 1000, 400), 400);
  assert.equal(proportionalScroll(10, 0, 400), 0);
  assert.equal(proportionalScroll(10, 100, 0), 0);
});

test('a draft written against an older revision keeps its own base', () => {
  assert.deepEqual(draftBase({ revision: 'r0' }, 'r1'), { revision: 'r0', stale: true });
  assert.deepEqual(draftBase({ revision: 'r1' }, 'r1'), { revision: 'r1', stale: false });
  assert.deepEqual(draftBase({}, 'r1'), { revision: 'r1', stale: false });
  assert.deepEqual(draftBase(null, 'r1'), { revision: 'r1', stale: false });
});

test('only relative or same-origin entry links are internal', () => {
  const base = 'http://127.0.0.1:8000/world';
  assert.deepEqual(entryLinkTarget('/world/entry?path=A.md', '/api/world', base), { path: 'A.md' });
  assert.deepEqual(entryLinkTarget('http://127.0.0.1:8000/world/entry?path=B.md', '/api/world', base), { path: 'B.md' });
  assert.equal(entryLinkTarget('https://example.com/world/entry?path=A.md', '/api/world', base), null);
  assert.equal(entryLinkTarget('//example.com/world/entry?path=A.md', '/api/world', base), null);
  assert.equal(entryLinkTarget('https://example.com/x?u=/world/entry', '/api/world', base), null);
  assert.equal(entryLinkTarget('https://example.com/api/world/entry?path=A.md', '/api/world', base), null);
});

test('drift inside a wikilink is skipped, drift touching one is not, and lines are counted', () => {
  const index = new Map([['alzerati', { from: 'alzerati', to: 'alzarati' }]]);
  const text = 'alzerati [[alzerati]] alzerati\n[[x]]alzerati\n\n[[y]]';
  const found = findDriftRanges(text, index).map((r) => r.start);
  assert.deepEqual(found, [0, 22, text.indexOf(']]alzerati') + 2]);
  const map = linkStatusMap([{ target: 'x', status: 'unresolved' }, { target: 'y', status: 'ambiguous', candidates: ['a.md'] }]);
  const problems = problemLinks(text, map);
  assert.deepEqual(problems.map((p) => p.line), [2, 4]);
  assert.equal(buildMarks(text, map, index).length, 5);
});

test('marks and line numbers agree with a naive scan on a large text', () => {
  const lines = [];
  for (let i = 0; i < 3000; i++) lines.push('line ' + i + ' [[Gone' + (i % 7) + ']] alzerati text');
  const text = lines.join('\n');
  const index = new Map([['alzerati', { from: 'alzerati', to: 'alzarati' }]]);
  const map = linkStatusMap([0, 1, 2, 3, 4, 5, 6].map((n) => ({ target: 'Gone' + n, status: 'unresolved' })));
  const problems = problemLinks(text, map);
  assert.equal(problems.length, 3000);
  problems.forEach((p) => assert.equal(p.line, text.slice(0, p.start).split('\n').length));
  assert.equal(findDriftRanges(text, index, findWikilinks(text)).length, 3000);
});

// -- Fake page ------------------------------------------------------------

function resetState() {
  Object.assign(state, {
    current: null, revision: null, savedText: '', lineEnding: '\n', dirty: false, preview: false,
    conflict: null, vaultId: null, nearby: null, kept: [], drawn: [], newDraft: null, retryIdea: null,
  });
  marks.resetForTests();
}

function entryFor(call, overrides) {
  const path = new URL(call.url, 'http://x').searchParams.get('path');
  return Object.assign({}, ENTRY, { path }, overrides);
}

// Delays the response to requests matching `when` until release() is called.
function holdRequests(when) {
  const inner = globalThis.fetch;
  const waiting = [];
  let holding = true;
  globalThis.fetch = (url, init) => {
    if (!holding || !when(url, init)) return inner(url, init);
    return new Promise((resolve) => waiting.push(() => resolve(inner(url, init))));
  };
  return {
    release() { holding = false; waiting.splice(0).forEach((go) => go()); },
    get count() { return waiting.length; },
  };
}

async function withPage(table, body) {
  const dom = installFakeDom();
  const calls = installFakeFetch(Object.assign({
    'GET /api/world/entry': reply(ENTRY),
    'GET /api/world/lexicon': reply(LEXICON),
    'GET /api/world/tree': reply({ entries: [], vault_id: 'v1' }),
    'POST /api/world/nearby': reply({ groups: {}, html: '<p>x</p>' }),
  }, table));
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); }, key: (i) => Array.from(store.keys())[i], get length() { return store.size; },
  };
  resetState();
  try {
    await body({ $: (id) => dom.document.getElementById(id), calls, dom });
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
  }
}

test('a draft older than the disk text keeps its base and Save meets the conflict review', async () => {
  let posts = [];
  const table = {
    'POST /api/world/entry': (call) => {
      posts.push(call.body);
      if (call.body.replace_revision) return reply({ revision: 'r3', generation: 6 });
      return { status: 409, body: { ok: false, message: 'Changed on disk.', data: { text: ENTRY.text, revision: 'r1' } } };
    },
  };
  await withPage(table, async ({ $ }) => {
    editor.initEditor();
    storage.writeDraft('People/Ada.md', { text: 'my older draft', revision: 'r0', updated: 'then' });
    await editor.openEntry('People/Ada.md');
    assert.equal($('entryText').value, 'my older draft');
    assert.equal(state.dirty, true);
    assert.equal(state.revision, 'r0', 'the draft keeps the revision it was written against');
    assert.equal(storage.readDraft('People/Ada.md').revision, 'r0', 'the stored draft still names its base');
    assert.match($('saveNotice').textContent, /written before this note last changed on disk/);
    assert.match($('saveNotice').textContent, /review both/);
    $('saveBtn').click();
    await settle(20);
    assert.equal(posts[0].revision, 'r0');
    assert.equal($('conflictPanel').hidden, false, 'the normal conflict review opens');
    assert.equal($('conflictDisk').textContent, ENTRY.text);
    assert.equal(storage.readDraft('People/Ada.md').revision, 'r0');
    $('replaceBtn').click();
    await settle(20);
    assert.deepEqual([posts[1].revision, posts[1].replace_revision], ['r0', 'r1']);
    assert.equal($('conflictPanel').hidden, true);
    assert.equal(state.revision, 'r3');
    assert.equal(state.dirty, false);
  });
});

test('Reload disk version after a stale-draft conflict keeps the draft in recovery', async () => {
  const table = {
    'POST /api/world/entry': { status: 409, body: { ok: false, message: 'x', data: { text: ENTRY.text, revision: 'r1' } } },
  };
  await withPage(table, async ({ $ }) => {
    editor.initEditor();
    storage.writeDraft('People/Ada.md', { text: 'my older draft', revision: 'r0', updated: 'then' });
    await editor.openEntry('People/Ada.md');
    $('saveBtn').click();
    await settle(20);
    $('reloadBtn').click();
    assert.equal($('entryText').value, ENTRY.text);
    assert.equal(state.revision, 'r1');
    assert.equal(storage.readRecovery('People/Ada.md').text, 'my older draft');
  });
});

test('a draft written against the current revision restores as before', async () => {
  await withPage({}, async ({ $ }) => {
    editor.initEditor();
    storage.writeDraft('People/Ada.md', { text: 'fresh draft', revision: 'r1', updated: 'now' });
    await editor.openEntry('People/Ada.md');
    assert.equal(state.revision, 'r1');
    assert.equal($('entryText').value, 'fresh draft');
    assert.match($('saveNotice').textContent, /Recovered an unsaved browser draft/);
  });
});

test('a failing draft store warns once, visibly', async () => {
  await withPage({}, async ({ $ }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    globalThis.localStorage.setItem = () => { throw new Error('QuotaExceededError'); };
    $('entryText').value = 'one';
    $('entryText').dispatch('input');
    assert.match($('saveNotice').textContent, /could not keep a copy of your draft/);
    assert.equal($('saveNotice').className.includes('error'), true);
    $('saveNotice').textContent = 'something else';
    $('entryText').value = 'two';
    $('entryText').dispatch('input');
    assert.equal($('saveNotice').textContent, 'something else', 'not repeated on every keystroke');
  });
});

test('a poll answered after a save does not overwrite the saved text', async () => {
  await withPage({}, async ({ $ }) => {
    const polls = [];
    const saved = globalThis.setInterval;
    globalThis.setInterval = (fn) => { polls.push(fn); return 0; };
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    globalThis.setInterval = saved;
    const held = holdRequests((url) => url.includes('/entry?'));
    const poll = polls[polls.length - 1]();
    await settle(5);
    assert.equal(held.count, 1);
    // A save lands while the poll is in flight.
    state.revision = 'r-saved';
    state.savedText = 'just saved';
    $('entryText').value = 'just saved';
    globalThis.fetch = globalThis.fetch; // keep the hold in place
    held.release();
    await poll;
    assert.equal($('entryText').value, 'just saved');
    assert.equal(state.revision, 'r-saved');
  });
});

test('a poll answered after another entry opened is dropped', async () => {
  await withPage({}, async ({ $ }) => {
    const polls = [];
    const saved = globalThis.setInterval;
    globalThis.setInterval = (fn) => { polls.push(fn); return 0; };
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    globalThis.setInterval = saved;
    const oldPoll = polls[polls.length - 1];
    const held = holdRequests((url) => url.includes('/entry?'));
    const pending = oldPoll();
    await settle(5);
    state.current = 'People/Other.md';
    state.revision = 'ro';
    $('entryText').value = 'other entry';
    state.savedText = 'other entry';
    held.release();
    await pending;
    assert.equal($('entryText').value, 'other entry');
  });
});

test('the last entry requested wins when opens finish out of order', async () => {
  const table = {
    'GET /api/world/entry': (call) => reply(entryFor(call, { text: 'text of ' + new URL(call.url, 'http://x').searchParams.get('path') })),
  };
  await withPage(table, async ({ $ }) => {
    editor.initEditor();
    const held = holdRequests((url) => url.includes('A.md'));
    const first = editor.openEntry('A.md');
    await settle(5);
    const second = editor.openEntry('B.md');
    await settle(5);
    assert.equal(state.current, 'B.md');
    held.release();
    assert.equal(await first, false, 'the superseded open reports it did not open');
    assert.equal(await second, true);
    await settle(10);
    assert.equal(state.current, 'B.md');
    assert.equal($('entryText').value, 'text of B.md');
  });
});

test('a Nearby answer that arrives after the next entry starts opening is discarded', async () => {
  await withPage({}, async ({ $ }) => {
    editor.initEditor();
    nearby.initNearby();
    await editor.openEntry('People/Ada.md');
    const held = holdRequests((url) => url.includes('/nearby'));
    emit(Events.DRAFT_CHANGED);
    await settle(600);
    assert.equal(held.count >= 1, true);
    emit(Events.ENTRY_OPENING);
    assert.equal(state.nearby, null);
    held.release();
    await settle(20);
    assert.equal(state.nearby, null, 'the old entry\'s suggestions were not applied');
    assert.equal($('nearbyGroups').children.length, 0);
  });
});

test('Split keeps the preview level with the editor', async () => {
  await withPage({}, async ({ $ }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    window.innerWidth = 1400;
    $('editorSplit').clientWidth = 900;
    $('previewBtn').click();
    assert.equal($('editorSplit').classList.contains('is-split'), true);
    Object.assign($('entryText'), { scrollTop: 500, scrollHeight: 1500, clientHeight: 500 });
    Object.assign($('previewPane'), { scrollTop: 0, scrollHeight: 1100, clientHeight: 300 });
    $('entryText').dispatch('scroll');
    $('entryText').dispatch('scroll');
    await settle(40);
    assert.equal($('previewPane').scrollTop, 400);
    // Without Split the panes are independent.
    $('previewBtn').click();
    $('editorSplit').classList.remove('is-split');
    $('previewPane').scrollTop = 7;
    $('entryText').scrollTop = 900;
    $('entryText').dispatch('scroll');
    await settle(40);
    assert.equal($('previewPane').scrollTop, 7);
  });
});

test('draft marks are cached until the text, links or drift change', async () => {
  await withPage({}, async () => {
    const text = 'see [[Nowhere]] here';
    marks.setEntryLinks([{ target: 'Nowhere', status: 'unresolved' }], 1);
    const first = marks.currentMarks(text);
    assert.equal(marks.currentMarks(text), first);
    assert.equal(marks.currentMarks(text + ' more') === first, false);
    const problems = marks.currentProblems(text);
    assert.equal(marks.currentProblems(text), problems);
    marks.setEntryLinks([], 1);
    assert.deepEqual(marks.currentMarks(text), []);
    assert.deepEqual(marks.currentProblems(text), []);
  });
});

test('drift is not fetched again for a generation it already asked for', async () => {
  const table = { 'GET /api/world/lexicon': reply({ generation: 5, entries: [], drift: [] }) };
  await withPage(table, async ({ calls }) => {
    const fetches = () => calls.filter((c) => c.path === '/api/world/lexicon').length;
    await marks.noteGeneration(7);
    await marks.noteGeneration(7);
    await marks.noteGeneration('7');
    assert.equal(fetches(), 1, 'a lexicon reporting its own generation does not cause refetching');
    await marks.noteGeneration(8);
    assert.equal(fetches(), 2);
  });
});

test('a newer generation noted during a drift fetch is fetched afterwards', async () => {
  await withPage({}, async ({ calls }) => {
    const fetches = () => calls.filter((c) => c.path === '/api/world/lexicon').length;
    const held = holdRequests((url) => url.includes('/lexicon'));
    const first = marks.noteGeneration(1);
    const second = marks.noteGeneration(2);
    await settle(5);
    held.release();
    await Promise.all([first, second]);
    await settle(10);
    assert.equal(fetches(), 2);
  });
});

test('saving a new draft twice at once makes one entry', async () => {
  const table = {
    'POST /api/world/new': reply({ path: 'Places/X.md', generation: 9 }),
    'GET /api/world/tags': reply({ tags: [] }),
    'GET /api/world/tree': (call) => (new URL(call.url, 'http://x').searchParams.get('path')
      ? reply({ entries: [] }) : reply({ vault_id: 'v1', entries: [{ name: 'Places', path: 'Places', is_dir: true }] })),
  };
  await withPage(table, async ({ $, calls }) => {
    editor.initEditor();
    create.initCreate();
    await create.openCreate({ title: 'X', folder: 'Places' });
    await settle(10);
    const held = holdRequests((url) => url.includes('/new'));
    $('saveBtn').click();
    await settle(5);
    $('saveBtn').click(); // a double click or a second Enter must not create twice
    held.release();
    await settle(60);
    assert.equal(calls.filter((c) => c.path === '/api/world/new').length, 1);
  });
});
