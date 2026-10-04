// Runs the real modules against a tiny fake DOM and fake server. This catches
// wiring mistakes (wrong ids, bad helper calls, broken flows) that the pure
// logic tests cannot; it is not a substitute for looking at the page.

import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

// Timers must not keep the test process alive (the editor polls every 12s).
const realSetInterval = globalThis.setInterval;
const realSetTimeout = globalThis.setTimeout;
globalThis.setInterval = (fn, ms) => { const t = realSetInterval(fn, ms); t.unref(); return t; };
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };

const { state } = await import('../static/world/state.js');
const editor = await import('../static/world/editor.js');
const tree = await import('../static/world/tree.js');
const create = await import('../static/world/create.js');
const { coverage } = await import('../static/world/coverage.js');
const { upkeep } = await import('../static/world/upkeep.js');
const { lexicon } = await import('../static/world/lexicon.js');
const { story } = await import('../static/world/story.js');
const { backlog } = await import('../static/world/backlog.js');

function fakeLocalStorage(initial) {
  const data = new Map(Object.entries(initial || {}));
  return {
    data,
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => { data.set(k, String(v)); },
    removeItem: (k) => { data.delete(k); },
    key: (i) => Array.from(data.keys())[i],
    get length() { return data.size; },
  };
}

function reply(data, message) {
  return { body: { ok: true, message: message || '', data } };
}

function query(call) {
  return new URL(call.url, 'http://x').searchParams;
}

const ENTRY = {
  path: 'People/Ada.md', revision: 'r1', text: 'Hello\r\nworld raiseed here',
  html: '<p>Hello</p>', entry: { title: 'Ada', words: 4 },
  backlinks: [{ path: 'B.md', title: 'B', context: 'mentions Ada' }],
  diagnostics: [],
};

function resetState() {
  Object.assign(state, {
    current: null, revision: null, savedText: '', lineEnding: '\n', dirty: false, preview: false,
    conflict: null, vaultId: null, nearby: null, kept: [], drawn: [], newDraft: null, retryIdea: null,
  });
}

// Sets up the fake page, then runs body with helpers.
async function withPage(routes, storageContents, body) {
  const dom = installFakeDom();
  globalThis.localStorage = fakeLocalStorage(storageContents);
  const calls = installFakeFetch(routes);
  resetState();
  try {
    await body({ $: (id) => dom.document.getElementById(id), calls, store: globalThis.localStorage });
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
  }
}

const entryRoutes = () => ({
  'GET /api/world/entry': reply(ENTRY),
  'GET /api/world/tree': reply({ entries: [], vault_id: 'v1' }),
  'POST /api/world/nearby': reply({ groups: {}, html: '<p>Hello</p>' }),
});

test('opening an entry fills the editor, heading and backlinks', async () => {
  await withPage(entryRoutes(), {}, async ({ $ }) => {
    editor.initEditor();
    assert.equal(await editor.openEntry('People/Ada.md'), true);
    assert.equal(state.current, 'People/Ada.md');
    assert.equal(state.lineEnding, '\r\n');
    assert.equal($('entryText').value, 'Hello\nworld raiseed here');
    assert.equal($('entryTitle').textContent, 'Ada');
    assert.equal($('entryFolder').textContent, 'People');
    assert.equal($('entryWords').textContent, '4 words');
    assert.equal($('entryPane').hidden, false);
    assert.equal($('welcome').hidden, true);
    assert.equal($('draftState').textContent, 'Saved');
    assert.equal($('backlinkCount').textContent, '(1)');
    assert.equal($('backlinkList').children[0].className, 'backlink-item');
  });
});

test('typing marks the draft dirty and stores it under the scoped key', async () => {
  await withPage(entryRoutes(), {}, async ({ $, store }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    $('entryText').value = 'Changed\nline';
    $('entryText').dispatch('input');
    assert.equal($('draftState').textContent, 'Unsaved draft');
    const stored = JSON.parse(store.getItem('rw:v2:local:default:draft:People/Ada.md'));
    assert.equal(stored.text, 'Changed\nline');
    assert.equal(stored.revision, 'r1');
  });
});

test('saving posts the text with its original line endings and clears the draft', async () => {
  const routes = entryRoutes();
  routes['POST /api/world/entry'] = reply({ revision: 'r2', recovery_path: 'recovery/Ada.md.1' }, 'Entry saved.');
  await withPage(routes, {}, async ({ $, calls, store }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    $('entryText').value = 'Changed\nline';
    $('entryText').dispatch('input');
    $('saveBtn').click();
    await new Promise((resolve) => setImmediate(resolve));
    const save = calls.find((c) => c.method === 'POST' && c.path === '/api/world/entry');
    assert.deepEqual(save.body, { path: 'People/Ada.md', text: 'Changed\r\nline', revision: 'r1' });
    assert.equal(state.revision, 'r2');
    assert.equal($('draftState').textContent, 'Saved');
    assert.equal(store.getItem('rw:v2:local:default:draft:People/Ada.md'), null);
    assert.equal($('saveNotice').textContent, 'Saved. Replaced bytes were preserved at recovery/Ada.md.1');
  });
});

test('a conflict shows both versions and Replace resubmits with the reviewed revision', async () => {
  const routes = entryRoutes();
  let saves = 0;
  routes['POST /api/world/entry'] = (call) => {
    saves += 1;
    if (saves === 1) return { status: 409, body: { ok: false, message: 'Changed on disk.', data: { text: 'disk text', revision: 'r9' } } };
    return reply({ revision: 'r10' });
  };
  await withPage(routes, {}, async ({ $, calls }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    $('entryText').value = 'my draft';
    $('entryText').dispatch('input');
    $('saveBtn').click();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal($('conflictPanel').hidden, false);
    assert.equal($('conflictDisk').textContent, 'disk text');
    assert.equal($('conflictDraft').textContent, 'my draft');
    $('replaceBtn').click();
    await new Promise((resolve) => setImmediate(resolve));
    const posts = calls.filter((c) => c.method === 'POST' && c.path === '/api/world/entry');
    assert.equal(posts[1].body.replace_revision, 'r9');
    assert.equal($('conflictPanel').hidden, true);
    assert.equal(state.revision, 'r10');
  });
});

test('an existing legacy draft is offered on open and migrated to the scoped key', async () => {
  const legacy = 'randomwords.world.draft.v1:People/Ada.md';
  const draft = { text: 'unsaved from before', revision: 'r1', updated: 'x' };
  await withPage(entryRoutes(), { [legacy]: JSON.stringify(draft) }, async ({ $, store }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    assert.equal($('entryText').value, 'unsaved from before');
    assert.equal(state.dirty, true);
    assert.equal($('saveNotice').textContent, 'Recovered an unsaved browser draft for this entry.');
    assert.equal(store.getItem(legacy), null);
    assert.equal(JSON.parse(store.getItem('rw:v2:local:default:draft:People/Ada.md')).text, 'unsaved from before');
  });
});

test('stageReplacement edits the open entry unsaved and selects the new text', async () => {
  await withPage(entryRoutes(), {}, async ({ $ }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    const start = $('entryText').value.indexOf('raiseed');
    const staged = await editor.stageReplacement(
      { path: 'People/Ada.md', revision: 'r1', start, end: start + 7, expected: 'raiseed' }, 'rainseed');
    assert.equal(staged, true);
    assert.equal($('entryText').value, 'Hello\nworld rainseed here');
    assert.deepEqual([$('entryText').selectionStart, $('entryText').selectionEnd], [start, start + 8]);
    assert.equal(state.dirty, true);
    assert.match($('saveNotice').textContent, /staged/i);
  });
});

test('stageReplacement refuses a stale span and leaves the text alone', async () => {
  await withPage(entryRoutes(), {}, async ({ $ }) => {
    editor.initEditor();
    await editor.openEntry('People/Ada.md');
    const staged = await editor.stageReplacement(
      { path: 'People/Ada.md', revision: 'OLD', start: 12, end: 19, expected: 'raiseed' }, 'rainseed',
      { stale: 'Refresh and retry.' });
    assert.equal(staged, false);
    assert.equal($('entryText').value, 'Hello\nworld raiseed here');
    assert.equal($('saveNotice').textContent, 'Refresh and retry.');
    assert.equal(state.dirty, false);
  });
});

test('openEntry can select a span once the entry is open', async () => {
  await withPage(entryRoutes(), {}, async ({ $ }) => {
    await editor.openEntry('People/Ada.md', { highlight: { start: 6, end: 11 } });
    assert.deepEqual([$('entryText').selectionStart, $('entryText').selectionEnd], [6, 11]);
  });
});

test('a failed open reports the server message and returns false', async () => {
  const routes = entryRoutes();
  routes['GET /api/world/entry'] = { status: 404, body: { ok: false, message: 'No such entry.' } };
  await withPage(routes, {}, async ({ $ }) => {
    assert.equal(await editor.openEntry('Nope.md'), false);
    assert.equal($('worldStatus').textContent, 'No such entry.');
  });
});

test('the tree lists the vault root and reports the connection', async () => {
  const routes = {
    'GET /api/world/tree': reply({
      vault_id: 'v1',
      entries: [{ name: 'People', path: 'People', is_dir: true }, { path: 'Ada.md', title: 'Ada', words: 12 }, { path: 'Stub.md', title: 'Stub', stub: true }],
    }),
  };
  await withPage(routes, {}, async ({ $ }) => {
    await tree.loadRoot();
    const rows = $('worldTree').children;
    assert.equal(rows.length, 3);
    assert.equal(rows[0].querySelector('.tree-toggle').textContent, '▸');
    assert.equal(rows[1].querySelector('.tree-count').textContent, '12');
    assert.equal(rows[2].querySelector('.tree-count').textContent, 'stub');
    assert.equal($('worldStatus').textContent, 'Vault connected');
    assert.equal(state.vaultId, 'v1');
  });
});

test('a new draft opens with its prefill as text and saves through POST /new', async () => {
  const routes = {
    'GET /api/world/tree': (call) => {
      const path = query(call).get('path');
      if (!path) return reply({ vault_id: 'v1', entries: [{ name: 'Places', path: 'Places', is_dir: true }] });
      return reply({ entries: [] });
    },
    'POST /api/world/new': reply({ path: 'Places/Harbor of Reeds.md', revision: 'rn', generation: 4 }),
    'GET /api/world/entry': (call) => (query(call).get('path') === 'Templates/T.md'
      ? reply({ path: 'Templates/T.md', text: '## Habitat\n\n## Uses' })
      : reply(Object.assign({}, ENTRY, { path: 'Places/Harbor of Reeds.md', entry: { title: 'Harbor of Reeds', words: 3 } }))),
    'POST /api/world/nearby': reply({ groups: {} }),
  };
  await withPage(routes, {}, async ({ $, calls, store }) => {
    editor.initEditor();
    create.initCreate();
    state.kept = ['moss'];
    await create.openCreate({
      title: 'Harbor of Reeds', folder: 'Places', fromTargets: ['Biomes/Marsh.md'],
      seeds: [{ word: 'rainseed', gloss: 'a lantern' }], tags: ['flora'], template: 'Templates/T.md', body: 'First draft.',
    });
    assert.equal($('draftTitle').value, 'Harbor of Reeds');
    assert.equal($('entryPane').hidden, false);
    assert.equal($('entryPane').classList.contains('is-new-draft'), true);
    assert.equal(state.current, null);
    assert.equal(state.newDraft.folder, 'Places');
    // The header lines, the tag, the body and the template are all plain text.
    assert.equal($('entryText').value,
      'From: [[Marsh]]\nOrigin: rainseed (a lantern), moss\n#flora\n\nFirst draft.\n\n## Habitat\n\n## Uses\n');
    assert.match($('placementSummary').textContent, /Places/);
    $('saveBtn').click();
    await new Promise((resolve) => setTimeout(resolve, 40));
    const post = calls.find((c) => c.method === 'POST' && c.path === '/api/world/new');
    assert.deepEqual(post.body, {
      folder: 'Places', title: 'Harbor of Reeds', body: $('entryText').value,
      from_targets: [], origin: [], tags: [], template: null,
    });
    assert.equal(state.current, 'Places/Harbor of Reeds.md');
    assert.equal(state.revision, 'rn');
    assert.equal(state.newDraft, null);
    assert.equal($('entryPane').classList.contains('is-new-draft'), false);
    assert.equal($('entryTitle').textContent, 'Harbor of Reeds');
    assert.deepEqual(JSON.parse(store.getItem('rw:v2:local:default:recent-folders:v1')).folders, ['Places']);
  });
});

test('a missing prefill folder leaves the draft without a folder and asks for another', async () => {
  const routes = {
    'GET /api/world/tree': (call) => (query(call).get('path')
      ? { status: 404, body: { ok: false, message: 'No such folder.' } }
      : reply({ entries: [] })),
    'GET /api/world/placement': reply({ kinds: ['Flora and Fauna'] }),
  };
  await withPage(routes, {}, async ({ $ }) => {
    editor.initEditor();
    create.initCreate();
    await create.openCreate({ folder: 'Gone' });
    await new Promise((resolve) => setTimeout(resolve, 20));
    assert.equal(state.newDraft.folder, null);
    assert.equal($('placementPanel').hidden, false);
    assert.match($('placementNote').textContent, /"Gone" is not in this vault/);
    $('saveBtn').click();
    await new Promise((resolve) => setTimeout(resolve, 10));
    assert.match($('placementIssue').textContent, /title/i);
  });
});

test('the report views render sample data', async () => {
  const routes = {
    'GET /api/world/matrix': reply({
      kinds: ['Flora'],
      rows: [{ path: 'Biomes/Marsh.md', title: 'Marsh', cells: { Flora: { count: 1, entries: [{ path: 'F.md', title: 'Reed', memberships: ['home'] }] } } }],
    }),
    'GET /api/world/health': reply({
      counts: { stubs: 2 },
      sections: { stubs: [{ path: 'S.md', title: 'S' }], spelling_drift: [{ from: 'raiseed', to: 'rainseed', occurrences: [{ path: 'A.md', line: 3, start: 1, end: 8, spelling: 'raiseed', context_before: 'the ', context_after: ' lamp', revision: 'r' }] }] },
    }),
    'GET /api/world/lexicon': reply({
      biomes: [{ path: 'Biomes/Marsh.md', title: 'Marsh' }],
      drift: [{ from: 'a', to: 'b', distance: 1, from_count: 1, to_count: 5, occurrences: [] }],
      entries: [{ word: 'rainseed', count: 2, spellings: [{ spelling: 'rainseed', count: 2 }], uses: [{ path: 'A.md', count: 2, biomes: ['Marsh'] }], which: { count: 1, texts: ['t.txt'] } }],
    }),
    'GET /api/world/story': reply({
      folders: ['Stories'], diagnostics: ['One warning'],
      appearances: [{ path: 'People/Ada.md', title: 'Ada', first_scene: 'S1.md', later_scenes: ['S2.md'] }],
      scenes: [{ path: 'S1.md', title: 'One', when: 1, where: [{ path: 'P.md', title: 'Harbor' }], who: [{ target: 'Nobody' }], appearances: [{ path: 'People/Ada.md', title: 'Ada' }] }],
    }),
    'GET /api/world/backlog': reply({ ideas: [{ path: 'Ideas.md', expected: 'A drowned bell rings.' }, { path: 'Ideas.md', expected: 'Done one', done: true }] }),
  };
  await withPage(routes, {}, async ({ $ }) => {
    await coverage.load({ force: true });
    const count = findAll($('coverageContent'), (n) => n.className === 'coverage-count')[0];
    assert.equal(count.textContent, '1');
    count.click();
    assert.equal(count.getAttribute('aria-expanded'), 'true');
    assert.equal($('coverageContent').dataset.loaded, 'yes');

    await upkeep.load({ force: true });
    assert.equal(findAll($('upkeepContent'), (n) => n.tagName === 'details').length, 2);
    assert.equal(findAll($('upkeepContent'), (n) => n.className === 'drift-occurrence').length, 1);

    $('lexiconBiome').appendChild(new Option('All biomes', ''));
    await lexicon.load({ force: true });
    assert.equal($('lexiconBiome').options.length, 2);
    assert.equal(findAll($('lexiconContent'), (n) => n.classList.contains('lexicon-entry')).length, 1);

    await story.load({ force: true });
    assert.equal(findAll($('storyContent'), (n) => n.classList.contains('story-scene')).length, 1);
    assert.equal(findAll($('storyContent'), (n) => n.className === 'story-unresolved').length, 1);

    await backlog.load({ force: true });
    const buttons = findAll($('backlogContent'), (n) => n.tagName === 'button').map((b) => b.textContent);
    assert.deepEqual(buttons, ['Start an entry', 'Open idea']);
  });
});

test('a report view shows the server error and can be retried', async () => {
  let attempts = 0;
  const routes = {
    'GET /api/world/matrix': () => {
      attempts += 1;
      return attempts === 1 ? { status: 500, body: { ok: false, message: 'Index unavailable.' } } : reply({ kinds: [], rows: [] });
    },
  };
  await withPage(routes, {}, async ({ $ }) => {
    await coverage.load({ force: true });
    assert.equal($('coverageContent').textContent, 'Index unavailable.');
    assert.equal($('coverageContent').dataset.loaded, 'no');
    await coverage.load();
    assert.equal($('coverageContent').dataset.loaded, 'yes');
    await coverage.load();
    assert.equal(attempts, 2, 'a loaded view is not fetched again without force');
  });
});

const nearby = await import('../static/world/nearby.js');
const autocomplete = await import('../static/world/autocomplete.js');
const bench = await import('../static/world/bench.js');

const settle = (ms) => new Promise((resolve) => setTimeout(resolve, ms || 0));

test('Nearby shows suggestions and Link match rewrites the named text', async () => {
  const routes = entryRoutes();
  routes['POST /api/world/nearby'] = (call) => {
    const text = call.body.text;
    const start = text.indexOf('raiseed');
    return reply({
      html: '<p>x</p>',
      groups: {
        named_not_linked: [{
          path: 'Things/Rainseed.md', title: 'Rainseed', start, end: start + 7, expected: 'raiseed',
          client_revision: call.body.client_revision, folder: 'Things', reason: 'named in text',
        }],
        same_biome: [{ path: 'Places/Marsh.md', title: 'Marsh', folder: 'Places' }],
      },
    });
  };
  await withPage(routes, {}, async ({ $ }) => {
    editor.initEditor();
    nearby.initNearby();
    await editor.openEntry('People/Ada.md');
    await settle(650);
    const groups = $('nearbyGroups').children;
    assert.equal(groups.length, 2);
    assert.equal($('nearbyState').textContent, 'Live suggestions');
    const link = findAll($('nearbyGroups'), (n) => n.classList.contains('link-suggestion'))[0];
    assert.equal(link.textContent, 'Link match');
    link.click();
    assert.equal($('entryText').value, 'Hello\nworld [[Rainseed|raiseed]] here');
    assert.equal(state.dirty, true);
  });
});

test('Link match does nothing when the draft changed after the suggestion', async () => {
  const routes = entryRoutes();
  routes['POST /api/world/nearby'] = (call) => {
    const start = call.body.text.indexOf('raiseed');
    return reply({ groups: { named_not_linked: [{
      path: 'Things/Rainseed.md', title: 'Rainseed', start, end: start + 7, expected: 'raiseed',
      client_revision: call.body.client_revision,
    }] } });
  };
  await withPage(routes, {}, async ({ $ }) => {
    editor.initEditor();
    nearby.initNearby();
    await editor.openEntry('People/Ada.md');
    await settle(650);
    $('entryText').value = 'Edited ' + $('entryText').value;
    const link = findAll($('nearbyGroups'), (n) => n.classList.contains('link-suggestion'))[0];
    link.click();
    assert.equal($('entryText').value, 'Edited Hello\nworld raiseed here');
    assert.equal($('nearbyState').textContent, 'Draft changed; refreshing suggestion');
  });
});

test('typing [[ offers matching entries and choosing one writes the wikilink', async () => {
  const routes = entryRoutes();
  routes['GET /api/world/search'] = reply({ results: [{ path: 'Places/Harbor.md', title: 'Harbor', folder: 'Places' }] });
  await withPage(routes, {}, async ({ $ }) => {
    editor.initEditor();
    autocomplete.initAutocomplete();
    await editor.openEntry('People/Ada.md');
    const field = $('entryText');
    field.value = 'She walked to [[Har';
    field.setSelectionRange(19, 19);
    field.dispatch('input');
    await settle(160);
    assert.equal($('autocomplete').hidden, false);
    assert.equal($('autocomplete').children.length, 1);
    $('autocomplete').children[0].dispatch('mousedown');
    assert.equal(field.value, 'She walked to [[Harbor]]');
    assert.equal($('autocomplete').hidden, true);
    assert.equal(field.selectionStart, field.value.length);
  });
});

test('the bench draws words, keeps them under the shared key, and starts an entry', async () => {
  const routes = {
    'GET /api/pools': reply({ pools: [{ name: 'Marsh words', path: 'dicts/marsh.txt' }] }),
    'POST /api/draw': reply({ drawn: ['loam', 'reed'] }),
    'GET /api/world/tree': reply({ entries: [] }),
    'GET /api/world/tags': reply({ tags: [] }),
  };
  await withPage(routes, { 'randomwords.kept.v1': JSON.stringify({ v: 1, words: ['moss'] }) }, async ({ $, calls, store }) => {
    create.initCreate();
    bench.initBench();
    assert.deepEqual(state.kept, ['moss']);
    assert.equal($('startFromKept').disabled, false);
    await settle(5);
    assert.equal($('benchPool').children.length, 1);
    $('drawCount').value = '2';
    $('drawWords').click();
    await settle(5);
    assert.deepEqual(calls.find((c) => c.path === '/api/draw').body, { count: 2 });
    const words = $('benchWords').children;
    assert.deepEqual(words.map((w) => w.textContent), ['loam', 'reed', 'moss']);
    words[0].click();
    assert.deepEqual(state.kept, ['moss', 'loam']);
    assert.deepEqual(JSON.parse(store.getItem('randomwords.kept.v1')), { v: 1, words: ['moss', 'loam'] });
    $('startFromKept').click();
    await settle(20);
    // Every kept word goes on the Origin: line of the new draft, ready to delete.
    assert.equal($('entryPane').hidden, false);
    assert.equal($('entryText').value, 'Origin: moss, loam\n\n');
  });
});
