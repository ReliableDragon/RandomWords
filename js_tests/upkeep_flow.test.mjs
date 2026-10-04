// Upkeep, Coverage, Lexicon, Backlog and Story flows against the fake page:
// staging links, dismissing with undo, creating from a row, and freshness.

import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

const realSetTimeout = globalThis.setTimeout;
const realSetInterval = globalThis.setInterval;
globalThis.setInterval = (fn, ms) => { const t = realSetInterval(fn, ms); t.unref(); return t; };
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };

const { state } = await import('../static/world/state.js');
const { upkeep } = await import('../static/world/upkeep.js');
const { coverage } = await import('../static/world/coverage.js');
const { lexicon } = await import('../static/world/lexicon.js');
const { story } = await import('../static/world/story.js');
const { rollPrompt } = await import('../static/world/backlog.js');
const { checkFreshness } = await import('../static/world/freshness.js');
const nav = await import('../static/world/nav.js');
const editor = await import('../static/world/editor.js');
const create = await import('../static/world/create.js');

const reply = (data) => ({ body: { ok: true, message: '', data } });
const settle = (ms) => new Promise((resolve) => realSetTimeout(resolve, ms || 5));
const buttons = (root, label) => findAll(root, (n) => n.tagName === 'button' && n.textContent === label);
const NOTE = 'Hello world Aitrip here and aitrip again';

function resetState() {
  Object.assign(state, {
    current: null, revision: null, savedText: '', lineEnding: '\n', dirty: false, preview: false,
    conflict: null, vaultId: null, nearby: null, kept: [], drawn: [], newDraft: null, retryIdea: null,
  });
}

function mention(over) {
  return Object.assign({
    source_path: 'A.md', source_title: 'A', target_path: 'Places/Aitrip.md', target_title: 'Aitrip',
    text: 'Aitrip', start: 12, end: 18, line: 1, context: NOTE, source_revision: 'r1',
    already_linked: false, exact_case: true, actionable: true,
    triage: { kind: 'mention', key: 'A.md|Places/Aitrip.md' },
    target_triage: { kind: 'target', key: 'Places/Aitrip.md' },
  }, over);
}

const HEALTH = {
  generation: 1,
  counts: { unlinked_mentions: 1, stubs: 1 },
  dismissed: { names_without_entry: 2, spelling_drift: 0, unlinked_mentions: 0 },
  mention_counts: [{ target_path: 'Places/Aitrip.md', target_title: 'Aitrip', notes: 1, mentions: 1 }],
  sections: {
    stubs: [{ path: 'S.md', title: 'S' }],
    unlinked_mentions: [
      mention({}),
      mention({ start: 23, end: 29, text: 'aitrip', exact_case: false, actionable: false,
        triage: { kind: 'mention', key: 'A.md|Places/Aitrip.md#2' } }),
    ],
    unresolved_links: [{ path: 'A.md', title: 'A', target: 'Nowhere', link_index: 0 }],
    names_without_entry: [{
      path: 'A.md', phrase: 'Fate Foulers', count: 2, sources: ['A.md'], context: 'the Fate Foulers came',
      triage: { kind: 'name', key: 'fate foulers' },
    }],
  },
};

const ENTRY = {
  path: 'A.md', revision: 'r1', text: NOTE, html: '<p>x</p>', entry: { title: 'A', words: 7 },
  backlinks: [], diagnostics: [],
};

function routes(extra) {
  return Object.assign({
    'GET /api/world/health': reply(HEALTH),
    'GET /api/world/entry': reply(ENTRY),
    'GET /api/world/tree': reply({ vault_id: 'v1', entries: [] }),
    'GET /api/world/tags': reply({ tags: [] }),
    'POST /api/world/nearby': reply({ groups: {} }),
    'POST /api/world/triage': reply({ dismissals: [], counts: {}, changed: true }),
    'GET /api/world/triage': reply({ dismissals: [], counts: {} }),
  }, extra);
}

async function withPage(table, body) {
  const dom = installFakeDom();
  globalThis.localStorage = {
    getItem: () => null, setItem() {}, removeItem() {}, key: () => null, length: 0,
  };
  const calls = installFakeFetch(table);
  resetState();
  try {
    await body({ $: (id) => dom.document.getElementById(id), calls });
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
  }
}

test('Upkeep puts unlinked mentions first, grouped, with non-actionable rows behind "Show all"', async () => {
  await withPage(routes(), async ({ $ }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    const headings = findAll(host, (n) => n.tagName === 'h3').map((n) => n.textContent);
    assert.deepEqual(headings.slice(0, 3), ['Named but not linked', 'Unresolved links', 'Names without entry']);
    const group = findAll(host, (n) => n.tagName === 'h4')[0];
    assert.equal(group.textContent, 'Aitrip — named in 1 note without a link');
    assert.equal(findAll(host, (n) => n.classList.contains('mention-row')).length, 1);
    assert.equal(findAll(host, (n) => n.tagName === 'mark')[0].textContent, 'Aitrip');
    buttons(host, 'Show all 2')[0].click();
    assert.equal(findAll(host, (n) => n.classList.contains('mention-row')).length, 2);
    assert.match(host.textContent, /different capitalization/);
    assert.equal(buttons(host, 'Stage link').length, 1, 'only the actionable row can be staged');
    assert.match(host.textContent, /2 dismissed/);
    buttons(host, 'Show only linkable')[0].click(); // the choice is remembered across reloads
    assert.equal(findAll(host, (n) => n.classList.contains('mention-row')).length, 1);
  });
});

test('Stage link opens the source and stages [[Target]] unsaved; a changed note is refused', async () => {
  await withPage(routes(), async ({ $ }) => {
    editor.initEditor();
    await upkeep.load({ force: true });
    buttons($('upkeepContent'), 'Stage link')[0].click();
    await settle(20);
    assert.equal(state.current, 'A.md');
    assert.equal($('entryText').value, 'Hello world [[Aitrip]] here and aitrip again');
    assert.equal(state.dirty, true);
  });
  const stale = routes();
  stale['GET /api/world/health'] = reply(Object.assign({}, HEALTH, {
    sections: Object.assign({}, HEALTH.sections, { unlinked_mentions: [mention({ source_revision: 'OLD' })] }),
  }));
  await withPage(stale, async ({ $ }) => {
    editor.initEditor();
    await upkeep.load({ force: true });
    buttons($('upkeepContent'), 'Stage link')[0].click();
    await settle(20);
    assert.equal($('entryText').value, NOTE);
    assert.match($('saveNotice').textContent, /Refresh Upkeep/);
  });
});

test('"Not in this note" removes the row at once, offers Undo, and Undo restores it', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    buttons(host, 'Not in this note')[0].click();
    await settle();
    const post = calls.filter((c) => c.path === '/api/world/triage' && c.method === 'POST')[0];
    assert.deepEqual(post.body, { action: 'dismiss', kind: 'mention', key: 'A.md|Places/Aitrip.md' });
    assert.equal(findAll(host, (n) => n.classList.contains('mention-row')).length, 0);
    const undo = buttons(host, 'Undo')[0];
    assert.ok(undo);
    assert.match(host.textContent, /Named but not linked01 dismissed/, 'count 1 -> 0, dismissed 0 -> 1');
    undo.click();
    await settle();
    assert.equal(calls.filter((c) => c.method === 'POST' && c.body.action === 'restore').length, 1);
    assert.equal(findAll(host, (n) => n.classList.contains('mention-row')).length, 1);
    assert.match(host.textContent, /Named but not linked10 dismissed/);
  });
});

test('"Never suggest" dismisses the whole target', async () => {
  await withPage(routes(), async ({ $, calls }) => {
    await upkeep.load({ force: true });
    buttons($('upkeepContent'), 'Never suggest')[0].click();
    await settle();
    const post = calls.filter((c) => c.method === 'POST' && c.path === '/api/world/triage')[0];
    assert.deepEqual(post.body, { action: 'dismiss', kind: 'target', key: 'Places/Aitrip.md' });
    assert.equal(findAll($('upkeepContent'), (n) => n.classList.contains('mention-group')).length, 0);
  });
});

test('a failed dismissal puts the row back with the reason', async () => {
  const failing = routes({ 'POST /api/world/triage': { status: 500, body: { ok: false, message: 'Disk full.' } } });
  await withPage(failing, async ({ $ }) => {
    await upkeep.load({ force: true });
    buttons($('upkeepContent'), 'Not a name')[0].click();
    await settle();
    assert.match($('upkeepContent').textContent, /Disk full\./);
    assert.equal(buttons($('upkeepContent'), 'Not a name').length, 1);
  });
});

test('Create entry from an unresolved link and a bare name prefills the title', async () => {
  await withPage(routes(), async ({ $ }) => {
    create.initCreate();
    await upkeep.load({ force: true });
    const sections = findAll($('upkeepContent'), (n) => n.tagName === 'details');
    const named = (key) => sections.filter((n) => n.dataset.key === key)[0];
    buttons(named('unresolved_links'), 'Create entry')[0].click();
    await settle(20);
    assert.equal($('draftTitle').value, 'Nowhere');
    buttons(named('names_without_entry'), 'Create entry')[0].click();
    await settle(20);
    assert.equal($('draftTitle').value, 'Fate Foulers');
    assert.equal(state.newDraft.title, 'Fate Foulers');
  });
});

test('Create entry on a qualified unresolved link starts the last segment in that folder', async () => {
  const health = Object.assign({}, HEALTH, {
    sections: Object.assign({}, HEALTH.sections, {
      unresolved_links: [{ path: 'A.md', title: 'A', target: 'Places/Harbor', link_index: 0 }],
    }),
  });
  await withPage(routes({ 'GET /api/world/health': reply(health) }), async ({ $ }) => {
    create.initCreate();
    await upkeep.load({ force: true });
    const sections = findAll($('upkeepContent'), (n) => n.tagName === 'details');
    buttons(sections.filter((n) => n.dataset.key === 'unresolved_links')[0], 'Create entry')[0].click();
    await settle(20);
    assert.equal(state.newDraft.title, 'Harbor');
    assert.equal(state.newDraft.folder, 'Places');
  });
});

test('Coverage cells, empty ones too, offer ＋ that starts an entry in that place', async () => {
  const cell = (count) => ({
    count, entries: [],
    create: { folder: 'Flora', from_target: 'Biomes/Marsh.md', template: 'Templates/Creature.md' },
  });
  const matrix = { kinds: ['Flora', 'Cultures'], generation: 1,
    rows: [{ path: 'Biomes/Marsh.md', title: 'Marsh', cells: { Flora: cell(0), Cultures: cell(8) } }] };
  await withPage(routes({ 'GET /api/world/matrix': reply(matrix) }), async ({ $ }) => {
    create.initCreate();
    await coverage.load({ force: true });
    const cells = findAll($('coverageContent'), (n) => n.tagName === 'td');
    assert.match(cells[0].className, /heat-0 is-thin/);
    assert.match(cells[1].className, /heat-4/);
    const add = findAll(cells[0], (n) => n.classList.contains('coverage-add'))[0];
    assert.equal(add.getAttribute('aria-label'), 'Start a Flora entry in Marsh');
    add.click();
    await settle(20);
    assert.equal($('entryPane').hidden, false);
    assert.equal(state.newDraft.folder, 'Flora');
    assert.equal(state.newDraft.template, 'Templates/Creature.md');
    assert.deepEqual(state.newDraft.fromTargets, [{ path: 'Biomes/Marsh.md', title: 'Marsh' }]);
    assert.match($('entryText').value, /^From: \[\[Marsh\]\]\n\n/);
    findAll(cells[1], (n) => n.classList.contains('coverage-count'))[0].click();
    assert.equal($('coverageContent').children[1].hidden, false);
    await settle(20);
  });
});

test('Start entry from this roll seeds words, places and the first line', async () => {
  const roll = {
    facet: 'Motivations', words: ['watchtower', 'verd'],
    entry: { path: 'Cultures/Deep Watchers.md', title: 'Deep Watchers', from_targets: ['Locations/L.md'] },
  };
  await withPage(routes({ 'POST /api/world/roll': reply(roll) }), async ({ $ }) => {
    create.initCreate();
    await rollPrompt({ entry: 'Cultures/Deep Watchers.md' });
    buttons($('rollCard'), 'Start entry from this roll')[0].click();
    await settle(20);
    assert.equal($('entryText').value,
      'From: [[L]]\nOrigin: watchtower, verd\n\nRelates to [[Cultures/Deep Watchers|Deep Watchers]]\n\n## Motivations\n\n');
    assert.deepEqual(state.newDraft.fromTargets, [{ path: 'Locations/L.md', title: 'L' }]);
  });
});

test('Story explains a missing --story-folder, and separately an empty configured folder', async () => {
  await withPage(routes({ 'GET /api/world/story': reply({ folders: [], scenes: [] }) }), async ({ $ }) => {
    await story.load({ force: true });
    assert.match($('storyContent').textContent, /--story-folder/);
    assert.match($('storyContent').textContent, /No story folders are set up/);
  });
  await withPage(routes({ 'GET /api/world/story': reply({ folders: ['Story'], scenes: [] }) }), async ({ $ }) => {
    await story.load({ force: true });
    assert.match($('storyContent').textContent, /Story is reading Story, but no notes there have story metadata/);
    assert.doesNotMatch($('storyContent').textContent, /No story folders are set up/);
  });
});

test('Lexicon shows readable library texts and dismisses drift and real words', async () => {
  const data = {
    generation: 1, biomes: [], dismissed: { entries: 0, drift: 1 },
    drift: [{
      from: 'alzerati', to: 'alzarati', distance: 1, from_count: 1, to_count: 5, occurrences: [],
      from_which: { count: 0, texts: [] }, to_which: { count: 1, texts: ['religion/bible.txt'] },
      triage: { kind: 'drift', key: 'alzerati→alzarati' },
    }],
    entries: [{
      word: 'rainseed', count: 2, spellings: [{ spelling: 'rainseed', count: 2 }], uses: [],
      which: { count: 1, texts: ['natural_history/marco_polo.txt'] }, triage: { kind: 'word', key: 'rainseed' },
    }],
  };
  await withPage(routes({ 'GET /api/world/lexicon': reply(data) }), async ({ $, calls }) => {
    $('lexiconBiome').appendChild(new Option('All biomes', ''));
    await lexicon.load({ force: true });
    const host = $('lexiconContent');
    assert.match(host.textContent, /Marco Polo \(natural history\)/);
    assert.match(host.textContent, /alzarati: 5 uses · In 1 library text: Bible \(religion\)/);
    assert.match(host.textContent, /1 dismissed/);
    buttons(host, 'Not drift')[0].click();
    buttons(host, 'Real word')[0].click();
    await settle();
    const kinds = calls.filter((c) => c.method === 'POST').map((c) => c.body.kind).sort();
    assert.deepEqual(kinds, ['drift', 'word']);
  });
});

test('a forced reload keeps open sections and the wrapper scroll; a failed background reload keeps the page', async () => {
  let fail = false;
  const table = routes({ 'GET /api/world/health': () => (fail
    ? { status: 500, body: { ok: false, message: 'Busy.' } } : reply(HEALTH)) });
  await withPage(table, async ({ $ }) => {
    await upkeep.load({ force: true });
    const stubs = () => findAll($('upkeepContent'), (n) => n.tagName === 'details' && n.dataset.key === 'stubs')[0];
    stubs().open = false;
    await upkeep.load({ force: true });
    assert.equal(stubs().open, false, 'the reader closed Stubs; a reload must not reopen it');
    fail = true;
    await upkeep.load({ force: true, background: true });
    assert.ok(stubs(), 'the old page is still there');
    assert.equal($('upkeepContent').dataset.loaded, 'no');
  });
});

test('freshness reloads the visible report when the generation moves and invalidates hidden ones', async () => {
  let generation = 1;
  let healthCalls = 0;
  const table = routes({
    'GET /api/world/health': () => { healthCalls += 1; return reply(Object.assign({}, HEALTH, { generation })); },
    'GET /api/world/matrix': () => reply({ kinds: [], rows: [], generation }),
    'GET /api/world/status': () => reply({ generation }),
  });
  await withPage(table, async ({ $ }) => {
    nav.registerView('upkeep', upkeep);
    await upkeep.load({ force: true });
    await coverage.load({ force: true });
    generation = 2;
    const plan = await checkFreshness();
    assert.equal(plan.upkeep, 'invalidate');
    assert.equal(plan.coverage, 'invalidate');
    assert.equal($('upkeepContent').dataset.loaded, 'no');
    nav.setWorldView('upkeep');
    await settle(20);
    assert.equal(upkeep.generation(), 2);
    const before = healthCalls;
    generation = 3;
    assert.deepEqual(await checkFreshness(), { upkeep: 'reload' });
    await settle(20);
    assert.equal(healthCalls, before + 1);
    assert.equal(upkeep.generation(), 3);
    assert.deepEqual(await checkFreshness(), {});
    nav.setWorldView('desk');
  });
});

const THREE_IN_A_NOTE = Object.assign({}, HEALTH, {
  counts: { unlinked_mentions: 4 },
  dismissed: { names_without_entry: 0, spelling_drift: 0, unlinked_mentions: 29 },
  dismissals: { names_without_entry: 0, spelling_drift: 0, unlinked_mentions: 1 },
  sections: {
    unlinked_mentions: [
      mention({ start: 12, end: 18 }),
      mention({ start: 30, end: 36 }),
      mention({ start: 50, end: 56 }),
      mention({ source_path: 'B.md', source_title: 'B',
        triage: { kind: 'mention', key: 'B.md|Places/Aitrip.md' } }),
    ],
  },
});

test('a note that names an entry three times shows one row with "+2 more in this note"', async () => {
  await withPage(routes({ 'GET /api/world/health': reply(THREE_IN_A_NOTE) }), async ({ $, calls }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    const rows = () => findAll(host, (n) => n.classList.contains('mention-row') && !n.hidden);
    assert.equal(rows().length, 2, 'A.md once, B.md once');
    assert.match(host.textContent, /\+2 more in this note/);
    const headline = findAll(host, (n) => n.classList.contains('report-count'))[0];
    assert.equal(headline.textContent, '2', 'the headline counts the rows shown, not the 4 mentions');
    assert.match(host.textContent, /1 dismissed \(hides 29 mentions\)/);
    assert.equal(buttons(host, 'Not this one').length, 0);
    buttons(host, 'Not in this note')[0].click();
    await settle();
    const post = calls.filter((c) => c.path === '/api/world/triage' && c.method === 'POST')[0];
    assert.deepEqual(post.body, { action: 'dismiss', kind: 'mention', key: 'A.md|Places/Aitrip.md' });
    assert.equal(rows().length, 1);
    assert.match(host.textContent, /2 dismissed \(hides 32 mentions\)/, 'that note\'s three mentions are hidden');
    buttons(host, 'Undo')[0].click();
    await settle();
    assert.match(host.textContent, /1 dismissed \(hides 29 mentions\)/);
    assert.equal(rows().length, 2);
  });
});

test('"Never suggest" adjusts the counts by the rows and mentions it hides', async () => {
  await withPage(routes({ 'GET /api/world/health': reply(THREE_IN_A_NOTE) }), async ({ $ }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    buttons(host, 'Never suggest')[0].click();
    await settle();
    assert.match(host.textContent, /2 dismissed \(hides 33 mentions\)/);
    assert.match(host.textContent, /Named but not linked0/);
  });
});

test('a name collision whose entry has no title still renders the Upkeep view', async () => {
  const data = Object.assign({}, HEALTH, {
    sections: Object.assign({}, HEALTH.sections, {
      name_collisions: [{
        name: 'Twin', kind: 'name', path: 'A/Twin.md', paths: ['A/Twin.md', 'B/Twin.md'],
        entries: [{ path: 'A/Twin.md', title: '', via: 'title' }, { path: 'B/Twin.md', via: 'alias' }],
      }],
    }),
  });
  await withPage(routes({ 'GET /api/world/health': reply(data) }), async ({ $ }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    assert.equal($('upkeepContent').dataset.loaded, 'yes');
    assert.match(host.textContent, /Name collisions/);
    assert.equal(buttons(host, 'Twin').length, 2, 'the title falls back to the file name');
  });
});

test('Start entry from this roll links a unique title by its title', async () => {
  const roll = { facet: 'Uses', words: [], entry: {
    path: 'Flora and Fauna/Forest-Jungle/Hozon/Honestree.md', title: 'Honestree', link: 'Honestree',
    from_targets: [] } };
  await withPage(routes({ 'POST /api/world/roll': reply(roll) }), async ({ $ }) => {
    create.initCreate();
    await rollPrompt();
    buttons($('rollCard'), 'Start entry from this roll')[0].click();
    await settle(20);
    assert.equal($('entryText').value, 'Relates to [[Honestree]]\n\n## Uses\n\n');
  });
});

test('a save during a freshness check triggers one more check, so reports never stay stale', async () => {
  let generation = 1;
  let statusCalls = 0;
  let release = null;
  const table = routes({
    'GET /api/world/health': () => reply(Object.assign({}, HEALTH, { generation })),
    'GET /api/world/status': () => reply({ generation }),
  });
  await withPage(table, async () => {
    // The first status answer is read, then held back: a stale answer in flight.
    const inner = globalThis.fetch;
    globalThis.fetch = async (url, init) => {
      const response = await inner(url, init);
      if (url.indexOf('/status') >= 0 && (statusCalls += 1) === 1) {
        await new Promise((resolve) => { release = resolve; });
      }
      return response;
    };
    nav.registerView('upkeep', upkeep);
    await upkeep.load({ force: true });
    nav.setWorldView('upkeep');
    const first = checkFreshness();
    await settle(20);
    generation = 2; // the save lands while that check is still waiting
    assert.deepEqual(await checkFreshness(), {}, 'a check already in flight answers at once');
    release();
    await first;
    await settle(60);
    assert.equal(statusCalls, 2, 'the dropped request ran once more');
    assert.equal(upkeep.generation(), 2);
    nav.setWorldView('desk');
  });
});
