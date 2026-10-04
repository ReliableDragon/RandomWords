// Editor flows against the fake page: conflicts, save events, merged Nearby
// cards, link status, drift underlines, split preview and autocomplete.

import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

const realSetInterval = globalThis.setInterval;
const realSetTimeout = globalThis.setTimeout;
globalThis.setInterval = (fn, ms) => { const t = realSetInterval(fn, ms); t.unref(); return t; };
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };

const { state } = await import('../static/world/state.js');
const { emit, Events, on } = await import('../static/world/events.js');
const editor = await import('../static/world/editor.js');
const marks = await import('../static/world/draft_marks.js');
const nearby = await import('../static/world/nearby.js');
const autocomplete = await import('../static/world/autocomplete.js');
const backdrop = await import('../static/world/backdrop.js');
const linkStatus = await import('../static/world/link_status.js');
const create = await import('../static/world/create.js');

const settle = (ms) => new Promise((resolve) => realSetTimeout(resolve, ms || 0));
const reply = (data) => ({ body: { ok: true, message: '', data } });

const LINKS = [
  { target: 'Glow', status: 'ambiguous', candidates: ['Flora/Glow.md', 'Fauna/Glow.md'] },
  { target: 'Nowhere', status: 'unresolved', candidates: [] },
  { target: 'Harbor', status: 'resolved', resolved_path: 'Places/Harbor.md', candidates: [] },
];

const ENTRY = {
  path: 'People/Ada.md', revision: 'r1', generation: 5,
  text: 'Ada saw [[Glow]] and [[Nowhere|the void]] near the alzerati.',
  html: '<p>Ada</p>', entry: { title: 'Ada', words: 10, from_targets: [{ target: 'Harbor' }] },
  links: LINKS, backlinks: [], diagnostics: [], skipped: ['table', 'image'],
};

const LEXICON = { generation: 5, entries: [], drift: [{ from: 'alzerati', to: 'alzarati', occurrences: [] }] };

function resetState() {
  Object.assign(state, {
    current: null, revision: null, savedText: '', lineEnding: '\n', dirty: false, preview: false,
    conflict: null, vaultId: null, nearby: null, kept: [], drawn: [], newDraft: null, retryIdea: null,
  });
  marks.resetForTests();
}

function routes(extra) {
  return Object.assign({
    'GET /api/world/entry': reply(ENTRY),
    'GET /api/world/lexicon': reply(LEXICON),
    'GET /api/world/tree': reply({ entries: [], vault_id: 'v1' }),
    'POST /api/world/nearby': reply({ groups: {}, html: '<p>x</p>' }),
  }, extra);
}

async function withPage(table, body) {
  const dom = installFakeDom();
  const calls = installFakeFetch(table);
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

async function openAda($) {
  editor.initEditor();
  backdrop.initBackdrop();
  linkStatus.initLinkStatus();
  await editor.openEntry('People/Ada.md');
  await settle(30);
}

test('Keep draft stops the 12 s poll re-raising the conflict for the same disk revision', async () => {
  const table = routes();
  let diskRevision = 'r2';
  table['GET /api/world/entry'] = () => reply(Object.assign({}, ENTRY, { revision: diskRevision, text: 'disk ' + diskRevision }));
  await withPage(table, async ({ $ }) => {
    const polls = [];
    const saved = globalThis.setInterval;
    globalThis.setInterval = (fn) => { polls.push(fn); return 0; };
    editor.initEditor();
    table['GET /api/world/entry'] = reply(ENTRY);
    await editor.openEntry('People/Ada.md');
    table['GET /api/world/entry'] = () => reply(Object.assign({}, ENTRY, { revision: diskRevision, text: 'disk ' + diskRevision }));
    globalThis.setInterval = saved;
    $('entryText').value = 'my draft';
    $('entryText').dispatch('input');
    const poll = polls[polls.length - 1];
    await poll();
    assert.equal($('conflictPanel').hidden, false);
    $('keepDraftBtn').click();
    assert.equal($('conflictPanel').hidden, true);
    await poll();
    assert.equal($('conflictPanel').hidden, true, 'same disk revision stays dismissed');
    diskRevision = 'r3';
    await poll();
    assert.equal($('conflictPanel').hidden, false, 'a newer disk revision raises it again');
  });
});

test('a successful save emits VAULT_CHANGED and refreshes backlinks, word count and links', async () => {
  const table = routes({ 'POST /api/world/entry': reply({ revision: 'r2', generation: 6 }) });
  await withPage(table, async ({ $, calls }) => {
    await openAda($);
    const seen = [];
    const off = on(Events.VAULT_CHANGED, (detail) => seen.push(detail));
    $('entryText').value = 'Ada saw [[Harbor]] now.';
    $('entryText').dispatch('input');
    table['GET /api/world/entry'] = reply(Object.assign({}, ENTRY, {
      revision: 'r2', generation: 6, entry: { title: 'Ada', words: 4 }, links: [LINKS[2]],
      backlinks: [{ path: 'B.md', title: 'B', context: 'x' }],
    }));
    $('saveBtn').click();
    await settle(30);
    off();
    assert.deepEqual(seen, [{ generation: 6, path: 'People/Ada.md' }]);
    assert.equal($('entryWords').textContent, '4 words');
    assert.equal($('backlinkCount').textContent, '(1)');
    assert.equal(marks.linksGeneration(), '6');
    assert.equal(calls.filter((c) => c.path === '/api/world/entry' && c.method === 'GET').length, 2);
  });
});

test('creating an entry emits VAULT_CHANGED with the response generation', async () => {
  const table = routes({
    'POST /api/world/new': reply({ path: 'Places/X.md', generation: 9 }),
    'GET /api/world/tags': reply({ tags: [] }),
  });
  table['GET /api/world/tree'] = (call) => (new URL(call.url, 'http://x').searchParams.get('path')
    ? reply({ entries: [] }) : reply({ vault_id: 'v1', entries: [{ name: 'Places', path: 'Places', is_dir: true }] }));
  await withPage(table, async ({ $ }) => {
    editor.initEditor();
    create.initCreate();
    await create.openCreate({ title: 'X', folder: 'Places' });
    await settle(10);
    const seen = [];
    const off = on(Events.VAULT_CHANGED, (detail) => seen.push(detail));
    $('saveBtn').click();
    await settle(40);
    off();
    assert.deepEqual(seen, [{ generation: 9, path: 'Places/X.md' }]);
  });
});

test('Nearby renders one merged card per entry with reasons and the right actions', async () => {
  const table = routes();
  table['POST /api/world/nearby'] = (call) => {
    const text = call.body.text;
    const start = text.indexOf('alzerati');
    return reply({
      html: '<p>x</p>', groups: { same_biome: [{ path: 'Old.md', title: 'Old' }] }, generation: 5,
      merged: [
        { path: 'Flora/Glow Fox.md', title: 'Glow Fox', folder: 'Flora', is_place: false, namesake: false, reasons: [
          { group: 'named_not_linked', text: 'Named as alzerati', start, end: start + 8, expected: 'alzerati',
            client_revision: call.body.client_revision, link_target: 'Glow Fox' },
          { group: 'same_tags', text: 'Shared tags: bright' }] },
        { path: 'Locations/Loch.md', title: 'Loch', folder: 'Locations', is_place: true, namesake: true, reasons: [
          { group: 'same_biome', text: 'Shared biome: Fenaya' }] },
      ],
    });
  };
  await withPage(table, async ({ $ }) => {
    const events = [];
    on(Events.NEARBY_UPDATED, (detail) => events.push(detail));
    editor.initEditor();
    nearby.initNearby();
    await editor.openEntry('People/Ada.md');
    await settle(650);
    const cards = findAll($('nearbyGroups'), (n) => n.classList.contains('nearby-card'));
    assert.equal(cards.length, 2);
    const labels = (card) => findAll(card, (n) => n.tagName === 'button').map((b) => b.textContent);
    assert.deepEqual(labels(cards[0]), ['Glow Fox', 'Link match', 'Insert link']);
    assert.deepEqual(labels(cards[1]), ['Loch', 'Insert link', 'Use as From']);
    const chips = findAll(cards[0], (n) => n.classList.contains('nearby-chip')).map((n) => n.textContent);
    assert.deepEqual(chips, ['Named as alzerati', 'Shared tags: bright']);
    assert.equal(findAll(cards[0], (n) => n.classList.contains('nearby-badge')).length, 0);
    assert.equal(findAll(cards[1], (n) => n.classList.contains('nearby-badge'))[0].textContent, 'Same name, different entry');
    assert.equal(events[0].groups.same_biome.length, 1);
    assert.equal(events[0].merged.length, 2);
    findAll(cards[0], (n) => n.classList.contains('link-suggestion'))[0].click();
    assert.match($('entryText').value, /\[\[Glow Fox\|alzerati\]\]/);
    assert.equal($('previewSkipped').hidden, true);
  });
});

test('Nearby keeps the polite live region and skipped note', async () => {
  const table = routes();
  table['POST /api/world/nearby'] = reply({ html: '<p>x</p>', groups: {}, merged: [], skipped: ['table', 'image'] });
  await withPage(table, async ({ $ }) => {
    editor.initEditor();
    nearby.initNearby();
    await editor.openEntry('People/Ada.md');
    await settle(650);
    assert.equal($('previewSkipped').textContent, 'Not rendered: tables, images');
    assert.equal($('previewSkipped').hidden, false);
    assert.match($('nearbyGroups').textContent, /No nearby entries yet/);
  });
});

test('the Links list names problem links and rewrites an ambiguous one safely', async () => {
  await withPage(routes(), async ({ $ }) => {
    await openAda($);
    await settle(10);
    assert.equal($('linkStatus').hidden, false);
    assert.equal($('linkStatusSummary').textContent, 'Links: 1 unresolved · 1 ambiguous');
    const rows = findAll($('linkStatusList'), (n) => n.classList.contains('link-problem'));
    assert.equal(rows.length, 2);
    const pick = findAll(rows[0], (n) => n.tagName === 'button')[1];
    assert.equal(pick.textContent, 'Fauna/Glow');
    pick.click();
    assert.equal($('entryText').value, 'Ada saw [[Fauna/Glow]] and [[Nowhere|the void]] near the alzerati.');
    assert.equal(state.dirty, true);
  });
});

test('an ambiguous rewrite is refused when the link has moved', async () => {
  await withPage(routes(), async ({ $ }) => {
    await openAda($);
    await settle(10);
    const pick = findAll($('linkStatusList'), (n) => n.tagName === 'button')[0];
    $('entryText').value = 'X' + $('entryText').value;
    pick.click();
    assert.equal($('entryText').value.indexOf('[[Glow]]') > 0, true);
    assert.match($('saveNotice').textContent, /That link changed/);
  });
});

test('an unresolved link offers Create entry with the entry\'s From targets', async () => {
  const table = routes({ 'GET /api/world/tags': reply({ tags: [] }) });
  await withPage(table, async ({ $ }) => {
    create.initCreate();
    await openAda($);
    await settle(10);
    const button = findAll($('linkStatusList'), (n) => n.tagName === 'button' && n.textContent === 'Create entry')[0];
    button.click();
    await settle(50);
    assert.equal($('entryPane').classList.contains('is-new-draft'), true);
    assert.equal($('draftTitle').value, 'Nowhere');
    assert.deepEqual(state.newDraft.fromTargets, [{ path: 'Places/Harbor.md', title: 'Harbor' }]);
    assert.match($('entryText').value, /^From: \[\[Harbor\]\]/);
  });
});

test('drift is underlined behind the textarea and the caret hint replaces it safely', async () => {
  await withPage(routes(), async ({ $ }) => {
    await openAda($);
    await settle(50);
    const marked = findAll($('entryBackdrop'), (n) => n.tagName === 'mark');
    assert.deepEqual(marked.map((n) => [n.className, n.textContent]), [
      ['mark-ambiguous', '[[Glow]]'], ['mark-unresolved', '[[Nowhere|the void]]'], ['mark-drift', 'alzerati'],
    ]);
    const at = $('entryText').value.indexOf('alzerati');
    $('entryText').setSelectionRange(at + 2, at + 2);
    $('entryText').dispatch('keyup');
    assert.equal($('driftHint').hidden, false);
    assert.equal($('driftHintText').textContent, 'alzerati → alzarati?');
    $('driftHintApply').click();
    await settle(20);
    assert.match($('entryText').value, /near the alzarati\.$/);
    assert.equal($('driftHint').hidden, true);
  });
});

test('the hint does not replace a word that changed under it', async () => {
  await withPage(routes(), async ({ $ }) => {
    await openAda($);
    await settle(50);
    const at = $('entryText').value.indexOf('alzerati');
    $('entryText').setSelectionRange(at + 2, at + 2);
    $('entryText').dispatch('keyup');
    $('entryText').value = 'XX' + $('entryText').value;
    $('driftHintApply').click();
    await settle(20);
    assert.match($('entryText').value, /alzerati\.$/);
    assert.match($('saveNotice').textContent, /That word changed/);
  });
});

test('drift is fetched once per generation', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    await openAda($);
    await editor.refreshEntryData();
    await settle(20);
    assert.equal(calls.filter((c) => c.path === '/api/world/lexicon').length, 1);
    await marks.noteGeneration(6);
    assert.equal(calls.filter((c) => c.path === '/api/world/lexicon').length, 2);
  });
});

test('the Preview button becomes Split on a wide editor and toggles both panes', async () => {
  await withPage(routes(), async ({ $ }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    window.innerWidth = 1400;
    $('editorSplit').clientWidth = 900;
    $('previewBtn').click();
    assert.equal($('previewBtn').textContent, 'Split');
    assert.equal($('previewBtn').getAttribute('aria-pressed'), 'true');
    assert.equal($('editorSplit').classList.contains('is-split'), true);
    assert.equal($('composeArea').hidden, false);
    assert.equal($('previewPane').hidden, false);
    $('previewBtn').click();
    assert.equal($('previewBtn').getAttribute('aria-pressed'), 'false');
    assert.equal($('previewPane').hidden, true);
  });
});

test('a narrow editor keeps the Preview and Edit toggle', async () => {
  await withPage(routes(), async ({ $ }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    window.innerWidth = 900;
    $('editorSplit').clientWidth = 600;
    $('previewBtn').click();
    assert.equal($('previewBtn').textContent, 'Edit');
    assert.equal($('composeArea').hidden, true);
    assert.equal($('entryPreview').hidden, false);
    $('previewBtn').click();
    assert.equal($('previewBtn').textContent, 'Preview');
    assert.equal($('composeArea').hidden, false);
  });
});

function typeInto($, text) {
  const field = $('entryText');
  field.value = text;
  field.setSelectionRange(text.length, text.length);
  field.dispatch('input');
}

test('a bare [[ lists Nearby cards without a request, and Enter is not taken until one is highlighted', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    editor.initEditor();
    autocomplete.initAutocomplete();
    await editor.openEntry('People/Ada.md');
    state.nearby = { merged: [
      { path: 'Flora/Glow Fox.md', title: 'Glow Fox', folder: 'Flora' }, { path: 'Places/Harbor.md', title: 'Harbor' }] };
    typeInto($, 'see [[');
    assert.equal($('autocomplete').hidden, false);
    assert.equal($('autocomplete').children.length, 2);
    assert.equal(calls.filter((c) => c.path === '/api/world/search').length, 0);
    assert.equal($('entryText').getAttribute('aria-expanded'), 'true');
    assert.equal($('entryText').getAttribute('aria-activedescendant'), null);
    let prevented = false;
    $('entryText').dispatch('keydown', { key: 'Enter', preventDefault() { prevented = true; } });
    assert.equal(prevented, false);
    $('entryText').dispatch('keydown', { key: 'ArrowDown' });
    assert.equal($('entryText').getAttribute('aria-activedescendant'), 'autocompleteOption0');
    $('entryText').dispatch('keydown', { key: 'Enter' });
    assert.equal($('entryText').value, 'see [[Glow Fox]]');
    assert.equal($('autocomplete').hidden, true);
    assert.equal($('entryText').getAttribute('aria-expanded'), 'false');
  });
});

test('Escape closes the list, and a burst of typing makes one search', async () => {
  const table = routes({ 'GET /api/world/search': reply({ results: [{ path: 'Places/Harbor.md', title: 'Harbor' }] }) });
  await withPage(table, async ({ $, calls }) => {
    editor.initEditor();
    autocomplete.initAutocomplete();
    await editor.openEntry('People/Ada.md');
    typeInto($, '[[H');
    typeInto($, '[[Ha');
    typeInto($, '[[Har');
    await settle(200);
    assert.equal(calls.filter((c) => c.path === '/api/world/search').length, 1);
    assert.equal($('autocomplete').hidden, false);
    assert.equal($('entryText').getAttribute('aria-activedescendant'), 'autocompleteOption0');
    $('entryText').dispatch('keydown', { key: 'Escape' });
    assert.equal($('autocomplete').hidden, true);
  });
});
