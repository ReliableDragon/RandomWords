// Write first, place later: a new unsaved draft in the editor, from the first
// keystroke to the saved entry. Runs the real modules on the fake page.

import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

const realSetInterval = globalThis.setInterval;
const realSetTimeout = globalThis.setTimeout;
globalThis.setInterval = (fn, ms) => { const t = realSetInterval(fn, ms); t.unref(); return t; };
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };

const { state, nearbyPath } = await import('../static/world/state.js');
const { Events, on } = await import('../static/world/events.js');
const editor = await import('../static/world/editor.js');
const create = await import('../static/world/create.js');
const placement = await import('../static/world/placement.js');
const nearby = await import('../static/world/nearby.js');
const backdrop = await import('../static/world/backdrop.js');
const marks = await import('../static/world/draft_marks.js');
const draftModule = await import('../static/world/new_draft.js');
const { storage } = await import('../static/world/storage.js');

const settle = (ms) => new Promise((resolve) => realSetTimeout(resolve, ms || 0));
const reply = (data) => ({ body: { ok: true, message: '', data } });
const query = (call) => new URL(call.url, 'http://x').searchParams;

const MARSH = { path: 'Locations/Biomes/Marsh.md', title: 'Marsh', folder: 'Locations/Biomes' };
const KINDS = ['Flora and Fauna', 'Locations'];
const CREATURE = 'Templates/Creature Template.md';

function resetState() {
  Object.assign(state, {
    current: null, revision: null, savedText: '', lineEnding: '\n', dirty: false, preview: false,
    conflict: null, vaultId: null, nearby: null, kept: [], drawn: [], newDraft: null, retryIdea: null,
  });
  marks.resetForTests();
  draftModule.resetForTests();
}

const SAVED = {
  path: 'Flora and Fauna/Reed.md', revision: 'r1', generation: 3, text: 'saved', html: '<p>x</p>',
  entry: { title: 'Reed', words: 5 }, links: [], backlinks: [], diagnostics: [],
};

function routes(extra) {
  return Object.assign({
    'GET /api/world/tree': (call) => {
      const path = query(call).get('path');
      if (path === 'Templates') {
        return reply({ entries: [{ path: CREATURE, name: 'Creature Template.md' }, { path: 'Templates/Place Template.md' }] });
      }
      if (path === 'Gone') return { status: 404, body: { ok: false, message: 'No such folder.' } };
      if (path) return reply({ entries: [] });
      return reply({ vault_id: 'v1', entries: [{ name: 'Flora and Fauna', path: 'Flora and Fauna', is_dir: true }] });
    },
    'GET /api/world/entry': (call) => {
      const path = query(call).get('path');
      if (path === CREATURE) return reply({ path, text: '## Description\n\n## Habitat\n', revision: 't1' });
      return reply(Object.assign({}, SAVED, { path }));
    },
    'GET /api/world/search': reply({ results: [MARSH] }),
    'GET /api/world/lexicon': reply({ generation: 1, entries: [], drift: [] }),
    'GET /api/world/placement': reply({
      kinds: KINDS, folder: 'Flora and Fauna', from_target: MARSH.path, template: CREATURE, suggested_kind: null,
    }),
    'POST /api/world/nearby': reply({ groups: {}, html: '<p>x</p>', generation: 1 }),
    'POST /api/world/new': (call) => reply({
      path: call.body.folder + '/' + call.body.title + '.md', revision: 'rn', generation: 4,
    }),
  }, extra);
}

async function withPage(table, body) {
  const dom = installFakeDom();
  const calls = installFakeFetch(table);
  const store = new Map();
  const sessionStore = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); }, key: (i) => Array.from(store.keys())[i], get length() { return store.size; },
  };
  globalThis.sessionStorage = {
    getItem: (k) => (sessionStore.has(k) ? sessionStore.get(k) : null),
    setItem: (k, v) => { sessionStore.set(k, String(v)); }, removeItem: (k) => { sessionStore.delete(k); },
    key: (i) => Array.from(sessionStore.keys())[i], get length() { return sessionStore.size; },
  };
  resetState();
  try {
    await body({ $: (id) => dom.document.getElementById(id), calls, store, sessionStore });
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
    delete globalThis.sessionStorage;
  }
}

// Wires the modules a draft touches, as main.js does.
function initDesk() {
  editor.initEditor();
  backdrop.initBackdrop();
  nearby.initNearby();
  create.initCreate();
}

function type($, text) {
  $('entryText').value = text;
  $('entryText').setSelectionRange(text.length, text.length);
  $('entryText').dispatch('input');
}

function setTitle($, title) {
  $('draftTitle').value = title;
  $('draftTitle').dispatch('input');
}

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

const chips = ($) => findAll($('placementKinds'), (n) => n.tagName === 'button');

// -- Opening ------------------------------------------------------------------

test('Start an entry opens the editor on an unsaved draft: no path, an inline title, kept words as Origin:', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    state.kept = ['uncouth', 'word-painter'];
    $('welcomeNew').click();
    await settle(30);
    assert.equal($('entryPane').hidden, false);
    assert.equal($('welcome').hidden, true);
    assert.equal($('entryPane').classList.contains('is-new-draft'), true);
    assert.equal(state.current, null);
    assert.equal($('entryText').value, 'Origin: uncouth, word-painter\n\n');
    assert.equal($('draftTitle').value, '');
    assert.equal($('draftState').textContent, 'New entry, not saved yet');
    assert.equal(nearbyPath(), 'Draft.md');
  });
});

test('every prefill source opens as text in the draft', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    // Nearby "Use as From" / Coverage: a From target and a template.
    await create.openCreate({ folder: 'Flora and Fauna', fromTargets: [MARSH.path], template: CREATURE });
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\n## Description\n\n## Habitat\n\n');
    assert.equal(state.newDraft.folder, 'Flora and Fauna');
    assert.deepEqual(state.newDraft.fromTargets, [{ path: MARSH.path, title: 'Marsh' }]);
    // A roll: seeds, a From target, the first line.
    await create.openCreate({
      seeds: [{ word: 'verd', gloss: 'green' }], fromTargets: [{ path: 'Locations/L.md', title: 'L' }],
      body: 'Relates to [[Deep Watchers]]\n\n## Uses\n\n',
    });
    assert.equal($('entryText').value, 'From: [[L]]\nOrigin: verd (green)\n\nRelates to [[Deep Watchers]]\n\n## Uses\n\n');
    // A backlog idea: a title, and the idea waits to be struck through.
    const idea = { path: 'Ideas.md', revision: 'r', start: 0, end: 3, expected: 'Isl' };
    await create.openCreate({ title: 'Island', idea });
    assert.equal($('draftTitle').value, 'Island');
    assert.equal($('entryText').value, '');
    assert.deepEqual(state.newDraft.idea, idea);
    // An unresolved link: a title and the folder its path named.
    await create.openCreate({ title: 'Harbor', folder: 'Flora and Fauna' });
    assert.equal(state.newDraft.title, 'Harbor');
    assert.equal(state.newDraft.folder, 'Flora and Fauna');
  });
});

test('a From target whose title another entry shares is written as a path', async () => {
  const table = routes({
    'GET /api/world/search': reply({ results: [
      { path: 'Locations/Biomes/Marsh.md', title: 'Marsh' }, { path: 'Flora and Fauna/Marsh.md', title: 'Marsh' },
    ] }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({ fromTargets: [MARSH.path] });
    assert.equal($('entryText').value, 'From: [[Locations/Biomes/Marsh]]\n\n');
  });
});

test('a later start replaces an earlier one that was still looking things up', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    const first = create.openCreate({ title: 'First', fromTargets: [MARSH.path] });
    const second = create.openCreate({ title: 'Second' });
    await Promise.all([first, second]);
    assert.equal(state.newDraft.title, 'Second');
  });
});

test('a start still looking things up gives up when the writer opens a note meanwhile', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    const hold = holdRequests((url) => url.startsWith('/api/world/search'));
    const pending = create.openCreate({ title: 'Late', fromTargets: [MARSH.path] });
    await settle(5);
    assert.equal(hold.count, 1, 'the From lookup is in flight');
    assert.equal(await editor.openEntry('Overview.md'), true);
    hold.release();
    await pending;
    assert.equal(state.newDraft, null, 'the late draft did not open');
    assert.equal(state.current, 'Overview.md');
    assert.equal($('entryPane').classList.contains('is-new-draft'), false);
  });
});

// -- Keeping the draft on this device -------------------------------------------

test('words and a title are kept in storage as they are written; an untouched draft is not', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ fromTargets: [MARSH.path] });
    assert.deepEqual(storage.listNewDrafts(), [], 'only the prefill: nothing worth keeping');
    type($, 'From: [[Marsh]]\n\nReeds bend.');
    const kept = storage.listNewDrafts();
    assert.equal(kept.length, 1);
    assert.equal(kept[0].text, 'From: [[Marsh]]\n\nReeds bend.');
    assert.equal($('draftState').textContent, 'Unsaved draft, kept on this device');
    assert.equal(state.dirty, true);
    setTitle($, 'Reed');
    assert.equal(storage.listNewDrafts()[0].title, 'Reed');
    // Back to nothing: the record goes.
    type($, 'From: [[Marsh]]\n\n');
    setTitle($, '');
    assert.deepEqual(storage.listNewDrafts(), []);
    assert.equal(state.dirty, false);
  });
});

test('reloading mid-draft brings back the text, title and placement', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna', fromTargets: [MARSH.path], template: CREATURE });
    state.newDraft.kind = 'Flora and Fauna';
    type($, 'From: [[Marsh]]\n\nMy words.');
    setTitle($, 'Reed');
    const sourceId = state.newDraft.id;
    // A reload: fresh page state, same browser storage.
    resetState();
    $('entryText').value = '';
    $('entryPane').classList.remove('is-new-draft');
    create.initCreate();
    assert.notEqual(state.newDraft.id, sourceId, 'a fresh document gets a private copy');
    assert.equal(draftModule.activeDraftId(), state.newDraft.id, 'this tab reloads its own copied id next');
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\nMy words.');
    assert.equal($('draftTitle').value, 'Reed');
    assert.equal(state.newDraft.folder, 'Flora and Fauna');
    assert.equal(state.newDraft.kind, 'Flora and Fauna');
    assert.equal(state.newDraft.template, CREATURE);
    assert.equal(state.current, null);
    assert.equal($('entryPane').hidden, false);
    assert.match($('saveNotice').textContent, /separate copy/);
    assert.deepEqual(storage.listNewDrafts().map((item) => item.text).sort(),
      ['From: [[Marsh]]\n\nMy words.', 'From: [[Marsh]]\n\nMy words.']);
  });
});

test('two document writers of one draft keep distinct visible copies through navigation and discard', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: '水辺' });
    type($, 'first tab: α');
    const firstId = state.newDraft.id;

    // A duplicated/new document inherits sessionStorage, but its in-memory
    // writer identity is fresh. Resuming the inherited id must clone first.
    resetState();
    assert.equal(editor.resumeNewDraft(firstId), true);
    const secondId = state.newDraft.id;
    assert.notEqual(secondId, firstId);
    assert.match($('saveNotice').textContent, /Both versions are kept/);
    type($, 'second tab: β');
    assert.deepEqual(storage.listNewDrafts().map((item) => item.text).sort(), ['first tab: α', 'second tab: β']);

    assert.equal(await editor.openEntry('Overview.md'), true);
    assert.deepEqual(storage.listNewDrafts().map((item) => item.id).sort(), [firstId, secondId].sort(),
      'navigation keeps both private copies');
    assert.equal(editor.resumeNewDraft(secondId), true);
    editor.discardNewDraft();
    assert.deepEqual(storage.listNewDrafts().map((item) => item.id), [firstId],
      'discard removes only this document writer\'s copy');
    assert.equal(storage.readNewDraft(firstId).text, 'first tab: α');
  });
});

test('saving one document writer leaves the other tab copy visible', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'First', folder: '' });
    type($, 'first tab');
    const firstId = state.newDraft.id;
    resetState();
    create.initCreate();
    assert.equal(editor.resumeNewDraft(firstId), true);
    const secondId = state.newDraft.id;
    state.newDraft.title = 'Second';
    type($, 'second tab');
    $('saveBtn').click();
    await settle(60);
    assert.equal(storage.readNewDraft(secondId), null);
    assert.equal(storage.readNewDraft(firstId).text, 'first tab');
  });
});

test('ownerless legacy drafts are cloned independently by concurrent document claims', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    storage.writeNewDraft('legacy-shared', {
      text: '', title: '空 🐚', folder: '', updated: '2026-10-03T09:00:00.000Z',
    });
    resetState();
    assert.equal(editor.resumeNewDraft('legacy-shared'), true);
    const firstCopy = state.newDraft.id;
    assert.equal($('entryText').value, '');
    resetState();
    assert.equal(editor.resumeNewDraft('legacy-shared'), true);
    const secondCopy = state.newDraft.id;
    assert.notEqual(firstCopy, secondCopy);
    assert.deepEqual(new Set(storage.listNewDrafts().map((item) => item.id)),
      new Set(['legacy-shared', firstCopy, secondCopy]));
  });
});

test('resuming an empty titleless legacy draft does not claim a second kept copy', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    storage.writeNewDraft('empty-legacy', {
      text: '', title: '', folder: '', updated: '2026-10-03T09:00:00.000Z',
    });
    assert.equal(editor.resumeNewDraft('empty-legacy'), true);
    assert.equal($('entryText').value, '');
    assert.equal($('saveNotice').hidden, true);
    assert.deepEqual(storage.listNewDrafts().map((item) => item.id), ['empty-legacy']);
  });
});

test('a clone write failure never removes or overwrites the source draft', async () => {
  await withPage(routes(), async ({ $, store }) => {
    initDesk();
    await create.openCreate({ title: 'Source' });
    type($, 'kept source');
    const sourceId = state.newDraft.id;
    resetState();
    const originalSet = globalThis.localStorage.setItem;
    globalThis.localStorage.setItem = () => { throw new Error('quota'); };
    assert.equal(editor.resumeNewDraft(sourceId), true);
    assert.notEqual(state.newDraft.id, sourceId);
    assert.match($('saveNotice').textContent, /earlier copy is still kept/);
    assert.equal(storage.readNewDraft(sourceId).text, 'kept source');
    editor.discardNewDraft();
    globalThis.localStorage.setItem = originalSet;
    assert.equal(storage.readNewDraft(sourceId).text, 'kept source');
    assert.ok(store.size > 0);
  });
});

test('a failed read does not create, overwrite or remove any draft', async () => {
  await withPage(routes(), async ({ store }) => {
    initDesk();
    storage.writeNewDraft('unreadable-now', {
      text: 'preserve me', title: '', folder: '', writer: 'another-document', updated: '2026-10-03T09:00:00.000Z',
    });
    const before = new Map(store);
    const originalGet = globalThis.localStorage.getItem;
    globalThis.localStorage.getItem = () => { throw new Error('blocked'); };
    assert.equal(editor.resumeNewDraft('unreadable-now'), false);
    globalThis.localStorage.getItem = originalGet;
    assert.deepEqual(store, before);
    assert.equal(storage.readNewDraft('unreadable-now').text, 'preserve me');
  });
});

test('navigation rechecks ownership and preserves an externally replaced key as a separate draft', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Mine' });
    type($, 'my current words');
    const sharedId = state.newDraft.id;
    storage.writeNewDraft(sharedId, {
      text: 'other tab words', title: 'Other', folder: '', writer: 'other-live-document',
      updated: '2026-10-03T09:00:01.000Z',
    });
    assert.equal(await editor.openEntry('Overview.md'), true);
    assert.deepEqual(storage.listNewDrafts().map((item) => item.text).sort(),
      ['my current words', 'other tab words']);
    assert.match($('saveNotice').textContent, /separate draft/);
  });
});

test('failed final persistence blocks every transition that would replace the open draft', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Current' });
    type($, 'last kept words');
    const currentId = state.newDraft.id;
    storage.writeNewDraft('other-draft', {
      text: 'other words', title: 'Other', folder: '', writer: 'other-document',
      updated: '2026-10-03T09:00:00.000Z',
    });
    const originalSet = globalThis.localStorage.setItem;
    globalThis.localStorage.setItem = () => { throw new Error('quota'); };
    type($, 'latest words only in the textarea');

    assert.equal(await editor.openEntry('Overview.md'), false);
    assert.equal(state.newDraft.id, currentId);
    assert.equal($('entryText').value, 'latest words only in the textarea');
    assert.equal(await create.openCreate({ title: 'Replacement' }), false);
    assert.equal(state.newDraft.id, currentId);
    assert.equal(editor.resumeNewDraft('other-draft'), false);
    assert.equal(state.newDraft.id, currentId);
    assert.match($('saveNotice').textContent, /could not keep a copy/);

    globalThis.localStorage.setItem = originalSet;
  });
});

test('resuming the current id reopens the final text persisted by the transition guard', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Current' });
    type($, 'earlier text');
    const id = state.newDraft.id;
    $('entryText').value = 'latest text before resume';
    assert.equal(editor.resumeNewDraft(id), true);
    assert.equal(state.newDraft.id, id);
    assert.equal($('entryText').value, 'latest text before resume');
    assert.equal(storage.readNewDraft(id).text, 'latest text before resume');
  });
});

test('discard stays on the draft when its kept copy cannot be removed', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Keep until removed' });
    type($, 'words');
    const id = state.newDraft.id;
    const originalRemove = globalThis.localStorage.removeItem;
    globalThis.localStorage.removeItem = () => { throw new Error('blocked'); };
    editor.discardNewDraft();
    assert.equal(state.newDraft.id, id);
    assert.equal($('entryText').value, 'words');
    assert.match($('saveNotice').textContent, /could not remove/);
    assert.equal(storage.readNewDraft(id).text, 'words');
    globalThis.localStorage.removeItem = originalRemove;
    editor.discardNewDraft();
    assert.equal(state.newDraft, null);
    assert.equal(storage.readNewDraft(id), null);
  });
});

test('clearing a kept draft blocks navigation until its stored copy can be removed', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    type($, 'words that were kept');
    const id = state.newDraft.id;
    const originalRemove = globalThis.localStorage.removeItem;
    globalThis.localStorage.removeItem = () => { throw new Error('blocked'); };
    type($, '');
    assert.equal(state.dirty, false);
    assert.equal(storage.readNewDraft(id).text, 'words that were kept');
    assert.equal(await editor.openEntry('Overview.md'), false);
    assert.equal(state.newDraft.id, id);
    assert.equal($('entryText').value, '');
    assert.match($('saveNotice').textContent, /could not keep a copy/);

    globalThis.localStorage.removeItem = originalRemove;
    assert.equal(await editor.openEntry('Overview.md'), true);
    assert.equal(storage.readNewDraft(id), null);
    assert.equal(state.current, 'Overview.md');
  });
});

test('clearing an empty local state never deletes a foreign record at the same id', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    type($, 'mine');
    const occupiedId = state.newDraft.id;
    storage.writeNewDraft(occupiedId, {
      text: 'foreign words', title: 'Foreign', folder: '', writer: 'other-document',
      updated: '2026-10-03T09:00:00.000Z',
    });
    type($, '');
    assert.notEqual(state.newDraft.id, occupiedId);
    assert.equal($('saveNotice').hidden, true, 'an empty local state does not claim a second kept copy');
    assert.equal(storage.readNewDraft(occupiedId).text, 'foreign words');
    assert.equal(await editor.openEntry('Overview.md'), true);
    assert.equal(storage.readNewDraft(occupiedId).text, 'foreign words');
  });
});

test('save completion never deletes edits persisted after its posted snapshot', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Reed', folder: 'Flora and Fauna' });
    type($, 'One.');
    const id = state.newDraft.id;
    const held = holdRequests((url) => url.includes('/new'));
    $('saveBtn').click();
    await settle(10);
    type($, 'One. Two.');
    setTitle($, 'Reed revised');
    assert.equal(await editor.openEntry('Overview.md'), true);
    held.release();
    await settle(80);
    assert.equal(state.current, 'Overview.md');
    assert.equal(storage.readNewDraft(id).text, 'One. Two.');
    assert.equal(storage.readNewDraft(id).title, 'Reed revised');
    assert.match($('saveNotice').textContent, /remain kept/);
  });
});

test('failed migration after an in-flight save retains the newer new-entry draft', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Reed', folder: 'Flora and Fauna' });
    type($, 'One.');
    const id = state.newDraft.id;
    const held = holdRequests((url) => url.includes('/new'));
    $('saveBtn').click();
    await settle(10);
    type($, 'One. Two.');
    const originalSet = globalThis.localStorage.setItem;
    globalThis.localStorage.setItem = () => { throw new Error('quota'); };
    held.release();
    await settle(80);
    assert.equal(state.current, 'Flora and Fauna/Reed.md');
    assert.equal($('entryText').value, 'One. Two.');
    assert.equal(storage.readNewDraft(id).text, 'One. Two.');
    assert.match($('saveNotice').textContent, /separate browser draft/);
    globalThis.localStorage.setItem = originalSet;
  });
});

test('a failed session pointer write uses its matching local fallback instead of a stale session id', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'First' });
    type($, 'first');
    const firstId = state.newDraft.id;
    const originalSessionSet = globalThis.sessionStorage.setItem;
    globalThis.sessionStorage.setItem = () => { throw new Error('session blocked'); };
    await create.openCreate({ title: 'Second' });
    type($, 'second');
    const secondId = state.newDraft.id;
    assert.notEqual(secondId, firstId);
    assert.equal(draftModule.activeDraftId(), secondId);
    globalThis.sessionStorage.setItem = originalSessionSet;
    resetState();
    assert.equal(draftModule.activeDraftId(), secondId);
    assert.equal(storage.readNewDraft(firstId).text, 'first');
    assert.equal(storage.readNewDraft(secondId).text, 'second');
  });
});

test('a draft that was saved or discarded does not come back on reload', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    type($, 'words');
    $('discardDraft').click();
    assert.equal($('discardConfirm').hidden, false, 'asks first, in the page');
    $('discardKeep').click();
    assert.equal(storage.listNewDrafts().length, 1, 'Keep it leaves the draft alone');
    $('discardDraft').click();
    $('discardYes').click();
    assert.deepEqual(storage.listNewDrafts(), []);
    assert.equal(state.newDraft, null);
    assert.equal($('welcome').hidden, false);
    assert.equal(draftModule.activeDraftId(), null);
  });
});

test('leaving for another entry keeps the draft and offers a way back', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Reed' });
    type($, 'Reeds bend.');
    const id = state.newDraft.id;
    assert.equal(await editor.openEntry('Overview.md'), true);
    assert.equal($('entryPane').classList.contains('is-new-draft'), false);
    assert.equal(state.newDraft, null);
    assert.equal(state.current, 'Overview.md');
    assert.equal(storage.listNewDrafts().length, 1);
    assert.match($('saveNotice').textContent, /"Reed" is not saved yet\. It is kept on this device\./);
    const back = findAll($('saveNotice'), (n) => n.tagName === 'button')[0];
    assert.equal(back.textContent, 'Back to the draft');
    back.click();
    assert.equal(state.newDraft.id, id);
    assert.equal($('entryText').value, 'Reeds bend.');
    assert.equal(state.current, null);
  });
});

test('opening an entry from an untouched draft leaves no draft behind', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ fromTargets: [MARSH.path] });
    await editor.openEntry('Overview.md');
    assert.deepEqual(storage.listNewDrafts(), []);
    assert.equal(findAll($('saveNotice'), (n) => n.tagName === 'button').length, 0);
  });
});

// -- Saving: the draft becomes the entry ------------------------------------------

test('saving turns the draft into the entry where it stands: same text, same caret, ENTRY_OPENED', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    const opened = [];
    const off = on(Events.ENTRY_OPENED, (detail) => opened.push(detail));
    await create.openCreate({ folder: 'Flora and Fauna', fromTargets: [MARSH.path] });
    type($, 'From: [[Marsh]]\n\nReeds bend in the wind.');
    $('entryText').setSelectionRange(20, 20);
    setTitle($, '  Reed ');
    $('saveBtn').click();
    await settle(60);
    off();
    const post = calls.find((c) => c.path === '/api/world/new');
    assert.deepEqual(post.body, {
      folder: 'Flora and Fauna', title: 'Reed', body: 'From: [[Marsh]]\n\nReeds bend in the wind.',
      from_targets: [], origin: [], tags: [], template: null,
    });
    assert.equal(state.current, 'Flora and Fauna/Reed.md');
    assert.equal(state.revision, 'rn');
    assert.equal(state.newDraft, null);
    assert.equal(state.dirty, false);
    // /new ends the file with a newline, and the editor mirrors the disk.
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\nReeds bend in the wind.\n');
    assert.equal(state.savedText, $('entryText').value);
    assert.equal($('entryText').selectionStart, 20, 'the caret stays where the writer left it');
    assert.equal($('entryPane').classList.contains('is-new-draft'), false);
    assert.equal($('entryTitle').textContent, 'Reed');
    assert.equal($('draftState').textContent, 'Saved');
    assert.deepEqual(storage.listNewDrafts(), []);
    assert.equal(draftModule.activeDraftId(), null);
    assert.equal(opened.length, 1);
    assert.equal(opened[0].path, 'Flora and Fauna/Reed.md');
    assert.equal(opened[0].title, 'Reed');
    assert.deepEqual(opened[0].entry, SAVED.entry);
    assert.deepEqual(opened[0].links, []);
    // The entry now saves like any other, against the revision the create returned.
    calls.length = 0;
  });
});

test('after saving, the next save is a normal revision-checked entry save', async () => {
  const table = routes({ 'POST /api/world/entry': reply({ revision: 'r2', generation: 5 }) });
  await withPage(table, async ({ $, calls }) => {
    initDesk();
    await create.openCreate({ title: 'Reed', folder: 'Flora and Fauna' });
    type($, 'One.');
    $('saveBtn').click();
    await settle(60);
    type($, 'One. Two.');
    $('saveBtn').click();
    await settle(60);
    const save = calls.find((c) => c.path === '/api/world/entry' && c.method === 'POST');
    assert.deepEqual(save.body, { path: 'Flora and Fauna/Reed.md', text: 'One. Two.', revision: 'rn' });
    assert.equal(state.revision, 'r2');
  });
});

test('words typed while the save is in flight stay unsaved on the new entry', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Reed', folder: 'Flora and Fauna' });
    type($, 'One.');
    const held = holdRequests((url) => url.includes('/new'));
    $('saveBtn').click();
    await settle(10);
    type($, 'One. Two.');
    held.release();
    await settle(80);
    assert.equal(state.current, 'Flora and Fauna/Reed.md');
    assert.equal(state.dirty, true);
    assert.equal(state.savedText, 'One.\n', 'what /new wrote, final newline included');
    assert.equal(storage.readDraft('Flora and Fauna/Reed.md').text, 'One. Two.');
  });
});

test('Save without a title asks for one, in the title field, and sends nothing', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna' });
    type($, 'words');
    $('saveBtn').click();
    await settle(20);
    assert.equal(calls.filter((c) => c.path === '/api/world/new').length, 0);
    assert.equal($('placementIssue').hidden, false);
    assert.equal($('placementIssue').textContent, 'Give this entry a title to save it.');
  });
});

test('Save without a folder opens the placement panel on the folder chooser, with the reason', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    await create.openCreate({ title: 'Reed' });
    type($, 'words');
    $('saveBtn').click();
    await settle(30);
    assert.equal(calls.filter((c) => c.path === '/api/world/new').length, 0);
    assert.equal($('placementPanel').hidden, false);
    assert.equal($('placementFolderChooser').hidden, false);
    assert.equal($('placementNote').textContent, 'Choose a folder for this entry to save it.');
  });
});

test('choosing a folder in the chooser selects it and Save then goes through', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    await create.openCreate({ title: 'Reed' });
    type($, 'words');
    $('saveBtn').click();
    await settle(30);
    const row = findAll($('folderBrowser'), (n) => n.tagName === 'button' && n.textContent.indexOf('Flora and Fauna') >= 0)[0];
    row.click();
    await settle(30);
    assert.equal(state.newDraft.folder, 'Flora and Fauna');
    assert.equal(state.newDraft.folderSource, 'chosen');
    assert.equal(nearbyPath(), 'Flora and Fauna/Reed.md');
    $('saveBtn').click();
    await settle(60);
    assert.equal(calls.find((c) => c.path === '/api/world/new').body.folder, 'Flora and Fauna');
  });
});

test('a title that is already taken says so, suggests another, and keeps the draft', async () => {
  const table = routes({
    'POST /api/world/new': { status: 409, body: { ok: false, message: 'That note exists.', data: { path: 'Flora and Fauna/Reed.md' } } },
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({ title: 'Reed', folder: 'Flora and Fauna' });
    type($, 'words');
    $('saveBtn').click();
    await settle(40);
    assert.match($('placementIssue').textContent,
      /already an entry called "Reed" in Flora and Fauna\. Give this one another title, such as "Reed 2"\./);
    assert.equal(state.newDraft.title, 'Reed');
    assert.equal(state.current, null);
    assert.equal(storage.listNewDrafts().length, 1);
  });
});

test('a backlog idea is struck through by the create, and a failed strike is offered for retry', async () => {
  const table = routes({
    'POST /api/world/new': reply({ path: 'Flora and Fauna/Reed.md', revision: 'rn', idea_updated: false, idea_error: 'Idea moved.' }),
  });
  await withPage(table, async ({ $, calls }) => {
    initDesk();
    const idea = { path: 'Ideas.md', revision: 'r', start: 0, end: 3, expected: 'Isl' };
    await create.openCreate({ title: 'Reed', folder: 'Flora and Fauna', idea });
    type($, 'words');
    $('saveBtn').click();
    await settle(60);
    assert.deepEqual(calls.find((c) => c.path === '/api/world/new').body.idea, idea);
    assert.equal(state.retryIdea.path, 'Ideas.md');
    assert.match($('saveNotice').textContent, /Idea moved\./);
  });
});

test('Create another like this saves, then opens a fresh draft with the same place, folder and template', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna', fromTargets: [MARSH.path], template: CREATURE });
    setTitle($, 'Reed');
    placement.openPlacementPanel();
    $('newRepeat').checked = true;
    $('newRepeat').dispatch('change');
    type($, $('entryText').value + 'Written.');
    $('saveBtn').click();
    await settle(80);
    assert.equal(state.current, null);
    assert.equal(state.newDraft.title, '');
    assert.equal(state.newDraft.folder, 'Flora and Fauna');
    assert.equal(state.newDraft.template, CREATURE);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\n## Description\n\n## Habitat\n\n');
    assert.match($('saveNotice').textContent, /Saved "Reed" as Flora and Fauna\/Reed\.md\./);
    assert.equal(findAll($('saveNotice'), (n) => n.textContent === 'Open the saved entry').length, 1);
    assert.deepEqual(storage.listNewDrafts(), [], 'the saved one is not kept as a draft');
  });
});

// -- Nearby on a draft ---------------------------------------------------------------

test('Nearby reads the draft as <folder>/<title>.md from the first keystroke', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna' });
    type($, 'The aurochult drifted.');
    await settle(650);
    const first = calls.filter((c) => c.path === '/api/world/nearby');
    assert.equal(first.length, 1);
    assert.equal(first[0].body.path, 'Flora and Fauna/Draft.md');
    assert.equal(first[0].body.text, 'The aurochult drifted.');
    setTitle($, 'Reed');
    await settle(650);
    const second = calls.filter((c) => c.path === '/api/world/nearby');
    assert.equal(second[second.length - 1].body.path, 'Flora and Fauna/Reed.md');
  });
});

test('a Nearby answer for an old title is dropped when the title changes while it is in flight', async () => {
  const table = routes({
    'POST /api/world/nearby': (call) => reply({
      groups: {}, html: '<p>x</p>', generation: 1,
      merged: [{ path: 'Flora/' + call.body.path + '.md', title: 'For ' + call.body.path, folder: 'Flora', reasons: [] }],
    }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna', title: 'Old' });
    const held = holdRequests((url) => url.includes('/nearby'));
    type($, 'Some words.');
    await settle(650);
    assert.equal(held.count, 1, 'the first request is out');
    setTitle($, 'New');
    held.release();
    await settle(30);
    assert.equal(state.nearby, null, 'the answer for Old.md was not applied');
    assert.equal(findAll($('nearbyGroups'), (n) => n.classList.contains('nearby-card')).length, 0);
    await settle(650);
    const card = findAll($('nearbyGroups'), (n) => n.classList.contains('nearby-title'))[0];
    assert.match(card.textContent, /Flora and Fauna\/New\.md/, 'the next request describes the new title');
  });
});

test('Use as From on a Nearby card adds the place to this draft instead of starting another', async () => {
  const table = routes({
    'POST /api/world/nearby': reply({
      groups: {}, html: '<p>x</p>', generation: 1,
      merged: [{ path: MARSH.path, title: 'Marsh', folder: 'Locations/Biomes', is_place: true, reasons: [] }],
    }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    const id = state.newDraft.id;
    type($, 'The marsh at dusk.');
    await settle(650);
    const use = findAll($('nearbyGroups'), (n) => n.tagName === 'button' && n.textContent === 'Use as From')[0];
    assert.match(use.getAttribute('aria-label'), /for this draft/);
    use.click();
    await settle(40);
    assert.equal(state.newDraft.id, id);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\nThe marsh at dusk.');
    assert.deepEqual(state.newDraft.fromTargets, [{ path: MARSH.path, title: 'Marsh' }]);
  });
});

// -- Link match, autocomplete and drift marks on a draft ----------------------------------

test('Link match works on a draft', async () => {
  const table = routes({
    'POST /api/world/nearby': (call) => {
      const start = call.body.text.indexOf('aurochult');
      return reply({
        groups: {}, html: '<p>x</p>', generation: 1,
        merged: [{ path: 'Flora/Aurochult.md', title: 'Aurochult', folder: 'Flora', reasons: [
          { group: 'named_not_linked', text: 'Named as aurochult (lowercase)', start, end: start + 9,
            expected: 'aurochult', client_revision: call.body.client_revision, link_target: 'Aurochult' }] }],
      });
    },
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    type($, 'The aurochult drifted.');
    await settle(650);
    findAll($('nearbyGroups'), (n) => n.classList.contains('link-suggestion'))[0].click();
    assert.equal($('entryText').value, 'The [[Aurochult|aurochult]] drifted.');
  });
});

test('a spelling-drift mark on a draft offers its replacement', async () => {
  const table = routes({
    'GET /api/world/lexicon': reply({ generation: 1, entries: [], drift: [{ from: 'alzerati', to: 'alzarati', occurrences: [] }] }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    await settle(30);
    type($, 'near the alzerati.');
    await settle(40);
    const marked = findAll($('entryBackdrop'), (n) => n.tagName === 'mark');
    assert.deepEqual(marked.map((n) => [n.className, n.textContent]), [['mark-drift', 'alzerati']]);
    const at = $('entryText').value.indexOf('alzerati');
    $('entryText').setSelectionRange(at + 2, at + 2);
    $('entryText').dispatch('keyup');
    assert.equal($('driftHint').hidden, false);
    $('driftHintApply').click();
    await settle(20);
    assert.equal($('entryText').value, 'near the alzarati.');
  });
});

// -- Placement: place, kind, folder, template ---------------------------------------------

test('picking a place writes the From: line and keeps the writer\'s caret in their words', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    await create.openCreate({});
    type($, 'Reeds bend.');
    $('entryText').setSelectionRange(5, 5);
    await placement.addFromPlace(MARSH, [MARSH]);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\nReeds bend.');
    assert.equal($('entryText').selectionStart, 5 + 'From: [[Marsh]]\n\n'.length);
    assert.match($('placementSummary').textContent, /From Marsh/);
    const ask = calls.find((c) => c.path === '/api/world/placement');
    assert.deepEqual(query(ask).get('from'), MARSH.path);
    // The same place twice is one link.
    await placement.addFromPlace(MARSH, [MARSH]);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\nReeds bend.');
  });
});

test('a kind proposes folder and template; the template goes in while the body is empty', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    initDesk();
    await create.openCreate({});
    await placement.addFromPlace(MARSH, [MARSH]);
    placement.openPlacementPanel();
    await settle(30);
    assert.deepEqual(chips($).map((c) => c.textContent), KINDS);
    chips($)[0].click();
    await settle(60);
    const ask = calls.filter((c) => c.path === '/api/world/placement').pop();
    assert.equal(query(ask).get('kind'), 'Flora and Fauna');
    assert.equal(state.newDraft.folder, 'Flora and Fauna');
    assert.equal(state.newDraft.folderSource, 'proposed');
    assert.equal(state.newDraft.template, CREATURE);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\n## Description\n\n## Habitat\n\n');
    assert.equal($('templateInsertEnd').hidden, true);
    assert.equal(chips($)[0].getAttribute('aria-pressed'), 'true');
    assert.match($('placementSummary').textContent, /Flora and Fauna.*Marsh.*Creature Template/);
    assert.equal($('entryText').selectionStart, 'From: [[Marsh]]\n\n## Description\n'.length + 1,
      'the caret moves under the first heading');
  });
});

test('once the writer has written, a template is offered at the end, never placed above', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna' });
    type($, 'My own words.');
    placement.openPlacementPanel();
    await placement.chooseTemplate(CREATURE);
    assert.equal($('entryText').value, 'My own words.');
    assert.equal($('templateInsertEnd').hidden, false);
    assert.equal(state.newDraft.template, CREATURE);
    $('templateInsertEnd').click();
    assert.equal($('entryText').value, 'My own words.\n\n## Description\n\n## Habitat\n');
    assert.equal($('templateInsertEnd').hidden, true);
  });
});

test('a different template replaces the one just inserted, until the writer adds anything', async () => {
  const table = routes({
    'GET /api/world/entry': (call) => {
      const path = query(call).get('path');
      if (path === CREATURE) return reply({ path, text: '## Description\n' });
      if (path === 'Templates/Place Template.md') return reply({ path, text: '## Layout\n' });
      return reply(SAVED);
    },
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna', fromTargets: [MARSH.path] });
    await placement.chooseTemplate(CREATURE);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\n## Description\n\n');
    await placement.chooseTemplate('Templates/Place Template.md');
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\n## Layout\n\n');
    type($, $('entryText').value + 'Typed.');
    await placement.chooseTemplate(CREATURE);
    assert.equal($('entryText').value, 'From: [[Marsh]]\n\n## Layout\n\nTyped.');
    assert.equal($('templateInsertEnd').hidden, false);
  });
});

test('a suggested folder that is not in the vault is not used, and the writer is told', async () => {
  const table = routes({
    'GET /api/world/placement': reply({ kinds: KINDS, folder: 'Gone', from_target: null, template: null, suggested_kind: null }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    placement.openPlacementPanel();
    await settle(30);
    chips($)[1].click();
    await settle(60);
    assert.equal(state.newDraft.folder, null);
    assert.match($('placementNote').textContent, /"Gone" is not in this vault yet/);
    assert.equal($('placementFolderChooser').hidden, false);
  });
});

test('a place pick does not move a folder the writer chose; a kind pick does', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ folder: 'Flora and Fauna' });
    state.newDraft.folderSource = 'chosen';
    state.newDraft.folder = 'Mine';
    await placement.addFromPlace(MARSH, [MARSH]);
    assert.equal(state.newDraft.folder, 'Mine');
  });
});

test('a place with no kind chosen suggests its most common kind', async () => {
  const table = routes({
    'GET /api/world/placement': reply({ kinds: KINDS, folder: null, from_target: MARSH.path, template: null, suggested_kind: 'Locations' }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    placement.openPlacementPanel();
    await placement.addFromPlace(MARSH, [MARSH]);
    await settle(30);
    assert.equal($('placementSuggest').hidden, false);
    assert.match($('placementSuggest').textContent, /Most entries from this place are Locations/);
    assert.match(chips($)[1].className, /is-suggested/);
  });
});

test('removing a place from the panel takes it off the From: line', async () => {
  await withPage(routes(), async ({ $ }) => {
    initDesk();
    await create.openCreate({ fromTargets: [MARSH.path] });
    placement.openPlacementPanel();
    const remove = findAll($('placeChosen'), (n) => n.classList.contains('placement-chip-remove'))[0];
    remove.click();
    assert.equal($('entryText').value, '');
    assert.deepEqual(state.newDraft.fromTargets, []);
  });
});

test('places are searched and listed first', async () => {
  const table = routes({
    'GET /api/world/search': reply({ results: [{ path: 'Flora/Reed.md', title: 'Reed' }, MARSH] }),
  });
  await withPage(table, async ({ $ }) => {
    initDesk();
    await create.openCreate({});
    placement.openPlacementPanel();
    $('placeSearch').value = 'ma';
    $('placeSearch').dispatch('input', { target: $('placeSearch') });
    await settle(300);
    const rows = findAll($('placeResults'), (n) => n.tagName === 'button');
    assert.deepEqual(rows.map((r) => r.children[0].textContent), ['Marsh', 'Reed']);
    rows[0].click();
    await settle(40);
    assert.match($('entryText').value, /^From: \[\[Marsh\]\]/);
  });
});
