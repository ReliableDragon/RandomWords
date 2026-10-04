// Upkeep's review queue: ordering and grouping, quick_edit's save rules, and
// the card's flow against the fake page.

import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

const realSetTimeout = globalThis.setTimeout;
const realSetInterval = globalThis.setInterval;
globalThis.setInterval = (fn, ms) => { const t = realSetInterval(fn, ms); t.unref(); return t; };
globalThis.setTimeout = (fn, ms) => { const t = realSetTimeout(fn, ms); t.unref(); return t; };

const { state } = await import('../static/world/state.js');
const { on, Events } = await import('../static/world/events.js');
const queue = await import('../static/world/review_queue.js');
const { quickApply } = await import('../static/world/quick_edit.js');
const nav = await import('../static/world/nav.js');
const { splitCommon, upkeep } = await import('../static/world/upkeep.js');

const reply = (data) => ({ body: { ok: true, message: '', data } });
const settle = (ms) => new Promise((resolve) => realSetTimeout(resolve, ms || 5));
const buttons = (root, label) => findAll(root, (n) => n.tagName === 'button' && n.textContent === label);

const NOTE = 'Hello world Aitrip here';
const REV = 'sha256:r1';

function mention(over) {
  return Object.assign({
    source_path: 'A.md', source_title: 'A', target_path: 'Places/Aitrip.md', target_title: 'Aitrip',
    text: 'Aitrip', start: 12, end: 18, line: 1, context: NOTE, source_revision: REV,
    already_linked: false, exact_case: true, actionable: true,
    triage: { kind: 'mention', key: 'A.md|Places/Aitrip.md' },
    target_triage: { kind: 'target', key: 'Places/Aitrip.md' },
  }, over);
}

function drift(over) {
  return Object.assign({
    from: 'alzerati', to: 'alzarati', distance: 1,
    triage: { kind: 'drift', key: 'alzerati→alzarati' },
    occurrences: [{
      path: 'D.md', revision: 'sha256:d1', spelling: 'Alzerati', line: 3, start: 10, end: 18,
      replacement: 'Alzarati', context_before: 'dawn in ', context_after: ' wakes',
    }],
  }, over);
}

const HEALTH = {
  generation: 1,
  counts: {},
  mention_counts: [
    { target_path: 'Places/Hozon.md', target_title: 'Hozon', notes: 2, mentions: 2 },
    { target_path: 'Places/Aitrip.md', target_title: 'Aitrip', notes: 1, mentions: 1 },
    { target_path: 'Stub2.md', target_title: 'Stub Two', notes: 5, mentions: 5 },
  ],
  sections: {
    unlinked_mentions: [
      mention({}),
      mention({ target_path: 'Places/Hozon.md', target_title: 'Hozon', text: 'Hozon', end: 17, source_path: 'B.md',
        triage: { kind: 'mention', key: 'B.md|Places/Hozon.md' }, target_triage: { kind: 'target', key: 'Places/Hozon.md' } }),
      mention({ target_path: 'Places/Hozon.md', target_title: 'Hozon', text: 'Hozon', end: 17, source_path: 'C.md',
        triage: { kind: 'mention', key: 'C.md|Places/Hozon.md' }, target_triage: { kind: 'target', key: 'Places/Hozon.md' } }),
      mention({ text: 'aitrip', exact_case: false, actionable: false }),
      mention({ source_path: 'E.md', already_linked: true, actionable: false }),
    ],
    unresolved_links: [{ path: 'A.md', title: 'A', target: 'Nowhere', link_index: 0, from_targets: ['Places/X.md'] }],
    spelling_drift: [drift({})],
    stubs: [
      { path: 'S1.md', title: 'S1', words: 5 },
      { path: 'Stub2.md', title: 'Stub Two', words: 2 },
      { path: 'S3.md', title: 'S3', words: 9 },
    ],
    notes_to_self: [{ path: 'N.md', title: 'N', text: 'Rewrite.', context: '${Rewrite.} It was', line: 3 }],
    name_collisions: [],
  },
};

// -- Pure helpers ------------------------------------------------------------

test('the queue runs mentions by target, then unresolved links, drift, stubs and notes', () => {
  const items = queue.buildQueue(HEALTH);
  assert.deepEqual(items.map((i) => i.type), [
    'mention', 'mention', 'mention', 'unresolved', 'drift', 'stub', 'stub', 'stub', 'note']);
  // Hozon is named in two notes, so it comes before Aitrip; its notes stay together.
  assert.deepEqual(items.slice(0, 3).map((i) => i.group.label + '/' + i.path), ['Hozon/B.md', 'Hozon/C.md', 'Aitrip/A.md']);
  // Lower-case and already-linked mentions are not in the queue.
  assert.equal(items.filter((i) => i.type === 'mention').length, 3);
});

test('the group being worked through stays in front even when another target now outranks it', () => {
  const all = queue.buildQueue(HEALTH);
  assert.equal(all[0].group.label, 'Hozon');
  // Hozon's first note is done; one note left against Aitrip's one: the natural order tips to Aitrip.
  const tipped = Object.assign({}, HEALTH, { mention_counts: [
    { target_path: 'Places/Hozon.md', target_title: 'Hozon', notes: 1, mentions: 1 },
    { target_path: 'Places/Aitrip.md', target_title: 'Aitrip', notes: 3, mentions: 3 },
  ] });
  assert.equal(queue.buildQueue(tipped)[0].group.label, 'Aitrip');
  assert.equal(queue.buildQueue(tipped, new Set(), 'm|Places/Hozon.md')[0].group.label, 'Hozon');
});

test('an unresolved item creates the last segment of a qualified target, in its folder', () => {
  const data = { sections: { unresolved_links: [
    { path: 'A.md', target: 'Places/Harbor', link_index: 0, from_targets: ['X.md'] },
    { path: 'A.md', target: 'Nowhere', link_index: 1 },
  ] } };
  const [qualified, bare] = queue.buildQueue(data);
  assert.deepEqual(qualified.create, { title: 'Harbor', folder: 'Places', fromTargets: ['X.md'] });
  assert.deepEqual(bare.create, { title: 'Nowhere', fromTargets: [] });
});

test('stubs the vault names most come first, and only the top few are queued', () => {
  const stubs = queue.buildQueue(HEALTH).filter((i) => i.type === 'stub').map((i) => i.title);
  assert.deepEqual(stubs, ['Stub Two', 'S3', 'S1']);
  const many = { sections: { stubs: Array.from({ length: 20 }, (_, n) => ({ path: n + '.md', title: 'T' + n, words: n })) } };
  assert.equal(queue.buildQueue(many).length, 8);
  assert.equal(queue.stubDetail({ words: 1 }, 1), '1 word · named without a link in 1 note');
});

test('a mention item carries the sentence with the proposed link and the span to edit', () => {
  const item = queue.buildQueue(HEALTH).find((i) => i.path === 'A.md' && i.type === 'mention');
  assert.deepEqual(item.sentence, { before: 'Hello world ', match: 'Aitrip', after: ' here', proposed: '[[Aitrip]]' });
  assert.deepEqual(item.span, { path: 'A.md', revision: REV, start: 12, end: 18, expected: 'Aitrip' });
  assert.deepEqual(item.dismissals.map((d) => d.label), ['Not in this note', 'Never suggest']);
  assert.equal(queue.primaryLabel(item), 'Link and save');
});

test('colliding titles get the qualified link', () => {
  const data = Object.assign({}, HEALTH, { sections: Object.assign({}, HEALTH.sections, {
    name_collisions: [{ entries: [{ path: 'Places/Aitrip.md' }, { path: 'Ideas/Aitrip.md' }] }],
  }) });
  const item = queue.buildQueue(data).find((i) => i.path === 'A.md' && i.type === 'mention');
  assert.equal(item.replacement, '[[Places/Aitrip|Aitrip]]');
});

test('drift items are one per occurrence and offer "Not drift"', () => {
  const item = queue.buildQueue(HEALTH).find((i) => i.type === 'drift');
  assert.equal(item.replacement, 'Alzarati');
  assert.equal(item.span.expected, 'Alzerati');
  assert.equal(item.group.label, 'alzerati → alzarati');
  assert.deepEqual(item.dismissals.map((d) => d.label), ['Not drift']);
});

test('skipped items leave the queue, and the summary counts the rest', () => {
  const all = queue.buildQueue(HEALTH);
  const left = queue.buildQueue(HEALTH, new Set([all[0].key]));
  assert.equal(left.length, all.length - 1);
  assert.equal(queue.queueSummary([all[0]]), '1 suggestion, about 1 minute');
  assert.match(queue.queueSummary(all), /^9 suggestions, about \d+ minutes$/);
  assert.equal(queue.estimateMinutes([]), 1);
});

test('progress reads "Hozon · note 2 of 3" and counts what the session already handled', () => {
  const items = queue.buildQueue(HEALTH);
  assert.equal(queue.groupProgress(items[0], items, {}).label, 'Hozon · note 1 of 2');
  const rest = items.slice(1);
  const progress = queue.groupProgress(rest[0], rest, { 'm|Places/Hozon.md': 1 });
  assert.equal(progress.label, 'Hozon · note 2 of 2');
  assert.equal(progress.fraction, 0.5);
});

test('the tally reads "8 linked · 3 skipped · 2 dismissed"', () => {
  assert.equal(queue.tallyText({ linked: 8, fixed: 0, skipped: 3, dismissed: 2, opened: 0 }), '8 linked · 3 skipped · 2 dismissed');
  assert.equal(queue.tallyText({ linked: 0, fixed: 0, skipped: 0, dismissed: 0, opened: 0 }), '');
});

test('Enter, S and Esc act on the queue only on Upkeep and never inside a field', () => {
  const scope = { drawerOpen: false, owns: () => true };
  const key = (k, over) => Object.assign({ key: k, target: { tagName: 'DIV' } }, over);
  assert.equal(queue.keyAction(key('Enter'), 'upkeep', scope), 'primary');
  assert.equal(queue.keyAction(key('s'), 'upkeep', scope), 'skip');
  assert.equal(queue.keyAction(key('S'), 'upkeep', scope), 'skip');
  assert.equal(queue.keyAction(key('Escape'), 'upkeep', scope), 'leave');
  assert.equal(queue.keyAction(key('Enter'), 'desk', scope), null);
  assert.equal(queue.keyAction(key('Enter'), 'upkeep'), null, 'without a scope nothing is the queue\'s');
  ['TEXTAREA', 'INPUT', 'SELECT', 'BUTTON', 'A', 'SUMMARY'].forEach((tag) => {
    ['Enter', 's', 'Escape'].forEach((k) => {
      assert.equal(queue.keyAction(key(k, { target: { tagName: tag } }), 'upkeep', scope), null, k + ' on ' + tag);
    });
  });
  assert.equal(queue.keyAction(key('s', { target: { tagName: 'DIV', isContentEditable: true } }), 'upkeep', scope), null);
  assert.equal(queue.keyAction(key('s', { metaKey: true }), 'upkeep', scope), null);
  assert.equal(queue.keyAction(key('s', { defaultPrevented: true }), 'upkeep', scope), null);
});

test('keys do nothing while the generator drawer is open or for a target outside the queue card', () => {
  const key = (k) => ({ key: k, target: { tagName: 'DIV' } });
  assert.equal(queue.keyAction(key('Enter'), 'upkeep', { drawerOpen: true, owns: () => true }), null);
  assert.equal(queue.keyAction(key('Escape'), 'upkeep', { drawerOpen: true, owns: () => true }), null);
  assert.equal(queue.keyAction(key('s'), 'upkeep', { drawerOpen: false, owns: () => false }), null);
});

test('a target belongs to the queue when it is in the card, or is the bare page', () => {
  const card = { parentNode: null };
  const inside = { parentNode: { parentNode: card } };
  const elsewhere = { parentNode: { parentNode: null } };
  const body = { parentNode: null };
  assert.equal(queue.ownsKey(inside, card, [body]), true);
  assert.equal(queue.ownsKey(body, card, [body]), true);
  assert.equal(queue.ownsKey(null, card, [body]), true);
  assert.equal(queue.ownsKey(elsewhere, card, [body]), false);
});

test('common words are split from names, and a missing flag counts as not common', () => {
  const { shown, common } = splitCommon([{ phrase: 'Despite', common: true }, { phrase: 'Zorp' }, { phrase: 'Hozon', common: false }]);
  assert.deepEqual(shown.map((i) => i.phrase), ['Zorp', 'Hozon']);
  assert.deepEqual(common.map((i) => i.phrase), ['Despite']);
});

// -- quick_edit --------------------------------------------------------------

async function withFetch(table, body) {
  const dom = installFakeDom();
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {}, key: () => null, length: 0 };
  const calls = installFakeFetch(table);
  Object.assign(state, { current: null, revision: null, dirty: false });
  Object.assign(queue.session, queue.newSession());
  try {
    await body({ $: (id) => dom.document.getElementById(id), calls });
  } finally {
    // Other test files share this process and the queue's module-level session.
    Object.assign(queue.session, queue.newSession());
    Object.assign(state, { current: null, revision: null, dirty: false });
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
  }
}

const SPAN = { path: 'A.md', revision: REV, start: 12, end: 18, expected: 'Aitrip' };
const entryRoute = (text, revision) => ({ 'GET /api/world/entry': reply({ path: 'A.md', text, revision }) });

test('quickApply replaces the span, writes with the revision it read and announces the change', async () => {
  const events = [];
  const off = on(Events.VAULT_CHANGED, (detail) => events.push(detail));
  await withFetch(Object.assign(entryRoute(NOTE, REV), {
    'POST /api/world/entry': reply({ revision: 'sha256:r2', generation: 7 }),
  }), async ({ calls }) => {
    const outcome = await quickApply(SPAN, '[[Aitrip]]');
    assert.deepEqual(outcome, { status: 'saved', revision: 'sha256:r2', generation: 7 });
    const post = calls.find((c) => c.method === 'POST');
    assert.deepEqual(post.body, { path: 'A.md', text: 'Hello world [[Aitrip]] here', revision: REV });
    assert.deepEqual(events, [{ generation: 7, path: 'A.md' }]);
  });
  off();
});

test('quickApply keeps CRLF files CRLF, with offsets counted after normalization', async () => {
  const crlf = 'Line one\r\nHello Aitrip here';
  const span = { path: 'A.md', revision: REV, start: 15, end: 21, expected: 'Aitrip' };
  await withFetch(Object.assign(entryRoute(crlf, REV), {
    'POST /api/world/entry': reply({ revision: 'r2', generation: 2 }),
  }), async ({ calls }) => {
    assert.equal((await quickApply(span, '[[Aitrip]]')).status, 'saved');
    assert.equal(calls.find((c) => c.method === 'POST').body.text, 'Line one\r\nHello [[Aitrip]] here');
  });
});

test('quickApply refuses a stale span: new revision or different text, nothing written', async () => {
  await withFetch(entryRoute(NOTE, 'sha256:other'), async ({ calls }) => {
    const outcome = await quickApply(SPAN, '[[Aitrip]]');
    assert.equal(outcome.status, 'stale');
    assert.match(outcome.message, /changed since Upkeep loaded/);
    assert.equal(calls.filter((c) => c.method === 'POST').length, 0);
  });
  await withFetch(entryRoute('Hello world Zorp here', REV), async ({ calls }) => {
    assert.equal((await quickApply(SPAN, '[[Aitrip]]')).status, 'stale');
    assert.equal(calls.filter((c) => c.method === 'POST').length, 0);
  });
});

test('quickApply never saves a note that has unsaved changes in the editor', async () => {
  await withFetch(entryRoute(NOTE, REV), async ({ calls }) => {
    Object.assign(state, { current: 'A.md', dirty: true });
    const outcome = await quickApply(SPAN, '[[Aitrip]]');
    assert.equal(outcome.status, 'dirty');
    assert.match(outcome.message, /unsaved changes in the editor/);
    assert.equal(calls.length, 0, 'it does not even read the note');
    // The same editor, clean, or another note, does not block.
    Object.assign(state, { current: 'A.md', dirty: false });
  });
  await withFetch(Object.assign(entryRoute(NOTE, REV), {
    'POST /api/world/entry': reply({ revision: 'r2', generation: 2 }),
  }), async () => {
    Object.assign(state, { current: 'Other.md', dirty: true });
    assert.equal((await quickApply(SPAN, '[[Aitrip]]')).status, 'saved');
  });
});

test('quickApply reports a 409 on save and other failures without throwing', async () => {
  await withFetch(Object.assign(entryRoute(NOTE, REV), {
    'POST /api/world/entry': { status: 409, body: { ok: false, message: 'Changed.', data: { text: 'x', revision: 'r9' } } },
  }), async () => {
    const outcome = await quickApply(SPAN, '[[Aitrip]]');
    assert.equal(outcome.status, 'conflict');
    assert.match(outcome.message, /saved somewhere else/);
  });
  await withFetch(Object.assign(entryRoute(NOTE, REV), {
    'POST /api/world/entry': { status: 500, body: { ok: false, message: 'Disk full.' } },
  }), async () => {
    assert.deepEqual(await quickApply(SPAN, '[[Aitrip]]'), { status: 'error', message: 'Disk full.' });
  });
  await withFetch({}, async () => {
    assert.equal((await quickApply(SPAN, '[[Aitrip]]')).status, 'error');
  });
});

// -- The card ----------------------------------------------------------------

function cardRoutes(extra) {
  return Object.assign({
    'GET /api/world/health': reply(HEALTH),
    'POST /api/world/triage': reply({ changed: true }),
  }, entryRoute(NOTE, REV), { 'POST /api/world/entry': reply({ revision: 'sha256:r2', generation: 3 }) }, extra);
}

function mountCard(data) {
  let reloads = 0;
  const card = queue.renderReviewCard(data || HEALTH, { reload: async () => { reloads += 1; } });
  return { card, reloads: () => reloads };
}

test('the idle card says how much there is and starts the queue', async () => {
  await withFetch(cardRoutes(), async () => {
    const { card } = mountCard();
    assert.match(card.textContent, /9 suggestions, about \d+ minutes/);
    buttons(card, 'Start reviewing')[0].click();
    assert.match(card.textContent, /Hozon · note 1 of 2/);
    assert.match(card.textContent, /Link and save/);
    assert.match(card.textContent, /Enter link and save · S skip · Esc leave/);
    // The marked change: the old text struck out and the link beside it.
    assert.equal(findAll(card, (n) => n.tagName === 'del')[0].textContent, 'Hozon');
    assert.equal(findAll(card, (n) => n.tagName === 'ins')[0].textContent, '[[Hozon]]');
  });
});

test('Skip moves on, tallies, and the keys drive the same actions', async () => {
  await withFetch(cardRoutes(), async () => {
    const { card } = mountCard();
    buttons(card, 'Start reviewing')[0].click();
    buttons(card, 'Skip')[0].click();
    assert.match(card.textContent, /Hozon · note 2 of 2/, 'a skipped note still counts towards the group');
    assert.match(card.textContent, /1 skipped/);
    buttons(card, 'Skip')[0].click();
    buttons(card, 'Skip')[0].click();
    assert.match(card.textContent, /Unresolved link/);
    buttons(card, 'Leave queue')[0].click();
    assert.match(card.textContent, /Resume reviewing/);
    assert.match(card.textContent, /3 skipped/);
    assert.match(card.textContent, /6 suggestions/);
  });
});

test('Link and save saves through quick_edit, tallies it and reloads the report', async () => {
  await withFetch(cardRoutes(entryRoute('Hello world Hozon here', REV)), async ({ calls }) => {
    const mounted = mountCard();
    const { card } = mounted;
    buttons(card, 'Start reviewing')[0].click();
    buttons(card, 'Link and save')[0].click();
    assert.match(card.textContent, /Working…/, 'buttons give way to a busy line while it saves');
    await settle(20);
    const post = calls.find((c) => c.method === 'POST' && c.path === '/api/world/entry');
    assert.deepEqual(post.body, { path: 'B.md', text: 'Hello world [[Hozon]] here', revision: REV });
    assert.equal(mounted.reloads(), 1);
    assert.match(card.textContent, /1 linked/);
  });
});

test('a stale note is not saved; the card says so and offers Open in editor', async () => {
  await withFetch(cardRoutes(entryRoute(NOTE, 'sha256:moved')), async ({ calls }) => {
    const { card } = mountCard();
    buttons(card, 'Start reviewing')[0].click();
    buttons(card, 'Link and save')[0].click();
    await settle(20);
    assert.match(card.textContent, /changed since Upkeep loaded/);
    assert.equal(buttons(card, 'Open in editor').length >= 1, true);
    assert.equal(calls.filter((c) => c.method === 'POST' && c.path === '/api/world/entry').length, 0);
    assert.match(card.textContent, /Hozon · note 1 of 2/, 'the item stays until the writer decides');
  });
});

test('a dismissal removes the item, offers Undo, and Undo brings it back', async () => {
  await withFetch(cardRoutes(), async ({ calls }) => {
    const mounted = mountCard();
    const { card } = mounted;
    buttons(card, 'Start reviewing')[0].click();
    buttons(card, 'Not in this note')[0].click();
    await settle(20);
    const post = calls.find((c) => c.method === 'POST' && c.path === '/api/world/triage');
    assert.deepEqual(post.body, { action: 'dismiss', kind: 'mention', key: 'B.md|Places/Hozon.md' });
    assert.match(card.textContent, /1 dismissed/);
    assert.match(card.textContent, /Hidden for this note/);
    buttons(card, 'Undo')[0].click();
    await settle(20);
    assert.deepEqual(calls.filter((c) => c.method === 'POST' && c.path === '/api/world/triage')[1].body,
      { action: 'restore', kind: 'mention', key: 'B.md|Places/Hozon.md' });
    assert.doesNotMatch(card.textContent, /1 dismissed/);
    assert.match(card.textContent, /Hozon · note 1 of 2/, 'the dismissed item is back in front');
    assert.equal(mounted.reloads(), 2);
  });
});

test('a refused dismissal keeps the item and shows the reason', async () => {
  await withFetch(cardRoutes({ 'POST /api/world/triage': { status: 500, body: { ok: false, message: 'Disk full.' } } }), async () => {
    const { card } = mountCard();
    buttons(card, 'Start reviewing')[0].click();
    buttons(card, 'Never suggest Hozon')[0].click();
    await settle(20);
    assert.match(card.textContent, /Disk full\./);
    assert.match(card.textContent, /Hozon · note 1 of 2/);
  });
});

test('an unsaved editor draft is not saved behind: the change is staged there instead', async () => {
  await withFetch(cardRoutes(), async ({ calls }) => {
    Object.assign(state, { current: 'B.md', dirty: true });
    const { card } = mountCard();
    buttons(card, 'Start reviewing')[0].click();
    buttons(card, 'Link and save')[0].click();
    await settle(20);
    assert.equal(calls.filter((c) => c.method === 'POST' && c.path === '/api/world/entry').length, 0);
    assert.match(card.textContent, /unsaved changes in the editor/);
  });
});

test('an empty queue says so, and the finished queue offers the full list', async () => {
  await withFetch(cardRoutes(), async () => {
    const empty = mountCard({ sections: {} });
    assert.match(empty.card.textContent, /Nothing to review/);
    assert.equal(buttons(empty.card, 'Start reviewing').length, 0);
    Object.assign(queue.session, queue.newSession());
    const small = mountCard({ sections: { notes_to_self: HEALTH.sections.notes_to_self } });
    buttons(small.card, 'Start reviewing')[0].click();
    buttons(small.card, 'Skip')[0].click();
    assert.match(small.card.textContent, /That is everything in the queue/);
    assert.match(small.card.textContent, /1 skipped/);
    buttons(small.card, 'Back to the full list')[0].click();
    assert.match(small.card.textContent, /Nothing to review|Start over/);
  });
});

test('Upkeep shows the queue first and hides common words behind a toggle', async () => {
  const health = Object.assign({}, HEALTH, {
    counts: { names_without_entry: 3 },
    sections: Object.assign({}, HEALTH.sections, {
      names_without_entry: [
        { path: 'A.md', phrase: 'Despite', count: 1, sources: ['A.md'], common: true, triage: { kind: 'name', key: 'despite' } },
        { path: 'A.md', phrase: 'Water', count: 1, sources: ['A.md'], common: true, triage: { kind: 'name', key: 'water' } },
        { path: 'A.md', phrase: 'Zorp', count: 1, sources: ['A.md'], triage: { kind: 'name', key: 'zorp' } },
      ],
    }),
  });
  await withFetch(cardRoutes({ 'GET /api/world/health': reply(health) }), async ({ $ }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    assert.equal(host.children[0].classList.contains('review-queue'), true);
    const names = findAll(host, (n) => n.tagName === 'details' && n.dataset.key === 'names_without_entry')[0];
    const heading = () => findAll(names, (n) => n.tagName === 'h4').map((n) => n.textContent);
    assert.deepEqual(heading(), ['Zorp']);
    assert.equal(names.querySelector('.report-count').textContent, '1');
    buttons(names, 'Show 2 common words')[0].click();
    assert.deepEqual(heading(), ['Despite', 'Water', 'Zorp']);
    assert.equal(names.querySelector('.report-count').textContent, '3');
    buttons(names, 'Hide common words')[0].click();
    assert.deepEqual(heading(), ['Zorp']);
  });
});

test('the card a reload builds is not left showing "Working…"', async () => {
  await withFetch(cardRoutes(entryRoute('Hello world Hozon here', REV)), async () => {
    let live = null;
    const mount = () => queue.renderReviewCard(HEALTH, { reload: async () => { live = mount(); } });
    live = mount();
    buttons(live, 'Start reviewing')[0].click();
    buttons(live, 'Link and save')[0].click();
    await settle(20);
    assert.doesNotMatch(live.textContent, /Working…/);
    assert.equal(buttons(live, 'Link and save').length, 1);
    assert.match(live.textContent, /1 linked/);
  });
});

// -- Keys on the live document -----------------------------------------------

test('Enter on a focused <summary>, with the drawer open, or on another view never runs a queue action', async () => {
  await withFetch(cardRoutes(entryRoute('Hello world Hozon here', REV)), async ({ calls, $ }) => {
    const { card } = mountCard();
    buttons(card, 'Start reviewing')[0].click();
    $('generatorDrawer').hidden = true; // the fake page starts every element unhidden
    nav.setWorldView('upkeep');
    try {
      const press = (k, target) => {
        let prevented = false;
        queue.handleKeydown({ key: k, target, preventDefault() { prevented = true; } });
        return prevented;
      };
      const summary = new (card.constructor)('summary');
      assert.equal(press('Enter', summary), false, 'a summary outside the card');
      const inner = card.querySelector('.review-active');
      assert.equal(press('s', inner), true, 'S inside the card skips');
      assert.match(card.textContent, /1 skipped/);
      assert.equal(press('Enter', globalThis.document.body), true, 'the bare page drives the queue');
      await settle(20);
      assert.equal(calls.filter((c) => c.method === 'POST' && c.path === '/api/world/entry').length, 1);
      // With the drawer open the hidden queue is left alone.
      $('generatorDrawer').hidden = false;
      const before = card.textContent;
      assert.equal(press('s', globalThis.document.body), false);
      assert.equal(press('Escape', globalThis.document.body), false);
      assert.equal(card.textContent, before);
      $('generatorDrawer').hidden = true;
      assert.equal(press('Escape', globalThis.document.body), true);
      assert.match(card.textContent, /Resume reviewing|Start reviewing/);
    } finally {
      nav.setWorldView('desk');
    }
  });
});

test('keys do nothing while another view is showing', async () => {
  await withFetch(cardRoutes(), async ({ $ }) => {
    const { card } = mountCard();
    buttons(card, 'Start reviewing')[0].click();
    $('generatorDrawer').hidden = true;
    nav.setWorldView('desk');
    let prevented = false;
    queue.handleKeydown({ key: 's', target: globalThis.document.body, preventDefault() { prevented = true; } });
    assert.equal(prevented, false);
    assert.doesNotMatch(card.textContent, /skipped/);
  });
});

// -- After a save ------------------------------------------------------------

test('a save keeps the card busy until a render from newer data arrives, so the next item is current', async () => {
  const twoInOneNote = (revision, spans) => ({
    generation: 1, counts: {}, mention_counts: [],
    sections: { spelling_drift: [drift({
      occurrences: spans.map(([start, end]) => ({
        path: 'D.md', revision, spelling: 'Alzerati', line: 1, start, end, replacement: 'Alzarati',
        context_before: 'a ', context_after: ' b',
      })),
    })] },
  });
  const first = twoInOneNote('sha256:d1', [[0, 8], [9, 17]]);
  const fresh = twoInOneNote('sha256:d2', [[9, 17]]);
  const text = 'Alzerati Alzerati';
  let saved = false;
  await withFetch(cardRoutes({
    'GET /api/world/entry': () => reply(saved
      ? { path: 'D.md', text: 'Alzarati Alzerati', revision: 'sha256:d2' }
      : { path: 'D.md', text, revision: 'sha256:d1' }),
    'POST /api/world/entry': () => { saved = true; return reply({ revision: 'sha256:d2', generation: 2 }); },
  }), async ({ calls }) => {
    let live = null;
    let loading = false;
    const mount = (data) => queue.renderReviewCard(data, {
      // Freshness's own load supersedes this one, so it resolves without rendering.
      reload: async () => { loading = true; },
      loading: () => loading,
    });
    live = mount(first);
    buttons(live, 'Start reviewing')[0].click();
    buttons(live, 'Fix and save')[0].click();
    await settle(20);
    assert.match(live.textContent, /Working…/, 'still busy: no newer data has been rendered');
    assert.equal(buttons(live, 'Fix and save').length, 0);
    // The newer render arrives from the other load.
    loading = false;
    const next = mount(fresh);
    await settle(20);
    assert.doesNotMatch(next.textContent, /Working…|changed since Upkeep loaded/);
    assert.match(next.textContent, /1 fixed/);
    // Linking the second spelling now uses the revision the save produced.
    buttons(next, 'Fix and save')[0].click();
    await settle(20);
    const posts = calls.filter((c) => c.method === 'POST' && c.path === '/api/world/entry');
    assert.equal(posts.length, 2, 'the second save was not refused as stale');
    assert.equal(posts[1].body.revision, 'sha256:d2');
    assert.doesNotMatch(next.textContent, /changed since Upkeep loaded/);
    loading = false;
    mount(fresh); // lets the second save's wait end before the next test
    await settle(10);
  });
});

test('if no newer render ever comes the card is released after the wait, and a failed reload releases it at once', async () => {
  queue.timing.renderWaitMs = 30;
  try {
    await withFetch(cardRoutes(entryRoute('Hello world Hozon here', REV)), async () => {
      const waiting = queue.renderReviewCard(HEALTH, { reload: async () => {}, loading: () => true });
      buttons(waiting, 'Start reviewing')[0].click();
      buttons(waiting, 'Link and save')[0].click();
      await settle(10);
      assert.match(waiting.textContent, /Working…/);
      await settle(60);
      assert.doesNotMatch(waiting.textContent, /Working…/);
      assert.match(waiting.textContent, /1 linked/);
    });
    await withFetch(cardRoutes(entryRoute('Hello world Hozon here', REV)), async () => {
      const failed = queue.renderReviewCard(HEALTH, { reload: async () => {}, loading: () => false });
      buttons(failed, 'Start reviewing')[0].click();
      buttons(failed, 'Link and save')[0].click();
      await settle(15);
      assert.doesNotMatch(failed.textContent, /Working…/);
    });
  } finally {
    queue.timing.renderWaitMs = 10000;
  }
});

// -- Focus -------------------------------------------------------------------

test('the card takes focus after the writer\'s own action, never after a background repaint', async () => {
  await withFetch(cardRoutes(), async () => {
    nav.setWorldView('upkeep');
    try {
      const focused = [];
      const realFocus = Object.getPrototypeOf(globalThis.document.body).focus;
      Object.getPrototypeOf(globalThis.document.body).focus = function focus() { focused.push(this.className); };
      try {
        const first = queue.renderReviewCard(HEALTH, { reload: async () => {} });
        buttons(first, 'Start reviewing')[0].click();
        await settle(10);
        assert.equal(focused.length, 1, 'Start reviewing focuses the card');
        // A background reload builds a new card from fresh data.
        const second = queue.renderReviewCard(HEALTH, { reload: async () => {} });
        await settle(10);
        assert.match(second.textContent, /Hozon/);
        assert.equal(focused.length, 1, 'a repaint nobody asked for leaves focus alone');
        buttons(second, 'Skip')[0].click();
        await settle(10);
        assert.equal(focused.length, 2, 'Skip focuses the next item');
      } finally {
        Object.getPrototypeOf(globalThis.document.body).focus = realFocus;
      }
    } finally {
      nav.setWorldView('desk');
    }
  });
});

test('a failed /health after a saved change leaves Upkeep showing, with the card usable', async () => {
  let healthCalls = 0;
  await withFetch(cardRoutes(Object.assign(entryRoute('Hello world Hozon here', REV), {
    'GET /api/world/health': () => {
      healthCalls += 1;
      return healthCalls === 1 ? reply(HEALTH) : { status: 500, body: { ok: false, message: 'Index is busy.' } };
    },
  })), async ({ $, calls }) => {
    await upkeep.load({ force: true });
    const host = $('upkeepContent');
    buttons(host, 'Start reviewing')[0].click();
    buttons(host, 'Link and save')[0].click();
    await settle(30);
    assert.equal(calls.filter((c) => c.method === 'POST' && c.path === '/api/world/entry').length, 1);
    assert.equal(healthCalls, 2);
    assert.doesNotMatch(host.textContent, /Index is busy/, 'the error did not replace the view');
    assert.equal(host.children[0].classList.contains('review-queue'), true);
    assert.doesNotMatch(host.textContent, /Working…/);
    assert.match(host.textContent, /1 linked/);
  });
});
