import test from 'node:test';
import assert from 'node:assert/strict';

import { heatLevel, maxCount, cellCreatePrefill } from '../static/world/coverage.js';
import { freshnessPlan } from '../static/world/freshness.js';
import { libraryTitle, whichSummary } from '../static/world/library.js';
import {
  collapseMentions, collidingPaths, groupHeading, groupMentions, mentionLink, mentionTotals,
  moreLabel, notActionableReason, splitContext, visibleMentions,
} from '../static/world/mentions.js';
import { rollLink, rollStart } from '../static/world/backlog.js';
import { storyEmptyState } from '../static/world/story.js';
import { dismissalLabel, dismissalText, filterDismissals } from '../static/world/triage.js';
import { orderSections, sectionLabel } from '../static/world/upkeep.js';

const mention = (over) => Object.assign({
  source_path: 'A.md', source_title: 'A', target_path: 'Places/Aitrip.md', target_title: 'Aitrip',
  text: 'Aitrip', start: 3, end: 9, line: 1, context: 'In Aitrip we', actionable: true,
  already_linked: false, exact_case: true,
  triage: { kind: 'mention', key: 'A.md|Places/Aitrip.md' },
  target_triage: { kind: 'target', key: 'Places/Aitrip.md' },
}, over);

test('context is split around the matched text, ignoring case as a fallback', () => {
  assert.deepEqual(splitContext('In Aitrip we', 'Aitrip'), ['In ', 'Aitrip', ' we']);
  assert.deepEqual(splitContext('In AITRIP we', 'aitrip'), ['In ', 'AITRIP', ' we']);
  assert.deepEqual(splitContext('nothing here', 'Aitrip'), ['nothing here', '', '']);
  assert.deepEqual(splitContext(undefined, undefined), ['', '', '']);
});

test('mentions group by target, linkable groups first and most-named first', () => {
  const rows = [
    mention({ source_path: 'B.md', target_path: 'Z.md', target_title: 'Zed', actionable: false }),
    mention({ source_path: 'A.md' }),
    mention({ source_path: 'B.md' }),
    mention({ source_path: 'B.md', target_path: 'Y.md', target_title: 'Why' }),
    mention({ source_path: 'A.md', already_linked: true, actionable: false }),
  ];
  const groups = groupMentions(rows, []);
  assert.deepEqual(groups.map((g) => g.target_title), ['Aitrip', 'Why', 'Zed']);
  assert.equal(groups[0].notes, 2);
  assert.equal(groups[0].actionable.length, 2);
  assert.equal(groups[0].others.length, 1);
  assert.equal(groupHeading(groups[0]), 'Aitrip — named in 2 notes without a link');
  assert.equal(groupHeading(groups[1]), 'Why — named in 1 note without a link');
  assert.equal(groupHeading(groups[2]), 'Zed — 1 mention, none to link');
});

test('the server\'s per-target note count wins over the row count', () => {
  const groups = groupMentions([mention({})], [{ target_path: 'Places/Aitrip.md', notes: 4, mentions: 5 }]);
  assert.equal(groupHeading(groups[0]), 'Aitrip — named in 4 notes without a link');
});

test('the staged link matches Nearby\'s form and qualifies colliding titles', () => {
  assert.equal(mentionLink(mention({ text: 'Aitrip' })), '[[Aitrip]]');
  assert.equal(mentionLink(mention({ text: 'the Aitrip' })), '[[Aitrip|the Aitrip]]');
  const colliding = collidingPaths([{ entries: [{ path: 'Places/Aitrip.md' }, { path: 'Ideas/Aitrip.md' }] }]);
  assert.equal(mentionLink(mention({ text: 'Aitrip' }), colliding), '[[Places/Aitrip|Aitrip]]');
});

test('rows that cannot be linked say why', () => {
  assert.equal(notActionableReason({ already_linked: true, exact_case: true }), 'already linked in this note');
  assert.equal(notActionableReason({ already_linked: false, exact_case: false }), 'different capitalization');
});

test('Upkeep lists the newest kinds first and keeps unknown sections after', () => {
  const sections = [['stubs', []], ['custom', []], ['unlinked_mentions', []], ['unresolved_links', []]];
  assert.deepEqual(orderSections(sections).map((s) => s[0]),
    ['unlinked_mentions', 'unresolved_links', 'stubs', 'custom']);
  assert.equal(sectionLabel('unlinked_mentions'), 'Named but not linked');
  assert.equal(sectionLabel('odd_kind'), 'odd kind');
});

test('heat levels: empty is 0 and the fullest cell is 4', () => {
  assert.equal(heatLevel(0, 40), 0);
  assert.equal(heatLevel(1, 40), 1);
  assert.equal(heatLevel(40, 40), 4);
  assert.equal(heatLevel(10, 40), 2);
  assert.equal(heatLevel(3, 0), 0);
  const rows = [{ cells: { A: { count: 2 }, B: { count: 7 } } }, { cells: { A: { count: 1 } } }];
  assert.equal(maxCount(rows, ['A', 'B', 'C']), 7);
});

test('a cell offers a create prefill only when the server described one', () => {
  assert.deepEqual(cellCreatePrefill({ create: { folder: 'Flora', from_target: 'B/M.md', template: 'T/C.md' } }),
    { folder: 'Flora', fromTargets: ['B/M.md'], template: 'T/C.md' });
  assert.deepEqual(cellCreatePrefill({ create: { folder: 'Flora', from_target: 'B/M.md', template: null } }),
    { folder: 'Flora', fromTargets: ['B/M.md'] });
  assert.equal(cellCreatePrefill({}), null);
});

test('a roll seeds the create form with its words, places and a linking first line', () => {
  const single = rollStart({
    facet: 'Motivations', words: ['watchtower', 'verd'],
    entry: { path: 'Cultures/Deep Watchers.md', title: 'Deep Watchers', from_targets: ['Locations/Lithoscarp.md'] },
  });
  assert.deepEqual(single.seeds, [{ word: 'watchtower', gloss: '' }, { word: 'verd', gloss: '' }]);
  assert.deepEqual(single.fromTargets, ['Locations/Lithoscarp.md']);
  assert.equal(single.body, 'Relates to [[Cultures/Deep Watchers|Deep Watchers]]\n\n## Motivations\n\n');
  const pair = rollStart({ facet: 'Rivalry', words: [], entry: [
    { path: 'A.md', title: 'A', from_targets: ['P.md'] }, { path: 'B.md', title: 'B', from_targets: ['Q.md'] }] });
  assert.equal(pair.body, '[[A]] × [[B]]\n\n## Rivalry\n\n');
  assert.deepEqual(pair.fromTargets, ['P.md']);
  assert.deepEqual(rollStart({ words: [] }), { seeds: [], fromTargets: [], body: '' });
});

test('library texts read as titles, with the topic folder in brackets', () => {
  assert.equal(libraryTitle('natural_history/marco_polo.txt'), 'Marco Polo (natural history)');
  assert.equal(libraryTitle('religion/bible.txt'), 'Bible (religion)');
  assert.equal(libraryTitle('notes.txt'), 'Notes');
  assert.equal(whichSummary({ count: 0, texts: [] }), '');
  assert.equal(whichSummary({ count: 1, texts: ['religion/bible.txt'] }), 'In 1 library text: Bible (religion)');
  assert.equal(whichSummary({ count: 6, texts: ['a/b.txt', 'a/c.txt', 'a/d.txt', 'a/e.txt'] }),
    'In 6 library texts: B (a), C (a), D (a), E (a) and 2 more');
});

test('freshness reloads the visible view, invalidates hidden ones and skips unloaded ones', () => {
  const view = (generation) => ({ generation: () => generation });
  const views = { upkeep: view(3), coverage: view(3), lexicon: view(4), story: view(null) };
  assert.deepEqual(freshnessPlan(views, 4, 'upkeep'), { upkeep: 'reload', coverage: 'invalidate' });
  assert.deepEqual(freshnessPlan(views, 4, 'desk'), { upkeep: 'invalidate', coverage: 'invalidate' });
  assert.deepEqual(freshnessPlan(views, undefined, 'upkeep'), {});
});

test('dismissals filter by kind, newest first, and read as sentences', () => {
  const rows = [
    { kind: 'name', key: 'fate foulers', dismissed_at: '2026-01-01' },
    { kind: 'mention', key: 'Notes/A.md|Places/Aitrip.md', dismissed_at: '2026-02-01' },
    { kind: 'target', key: 'Places/Hozon.md', dismissed_at: '2026-03-01' },
  ];
  assert.deepEqual(filterDismissals(rows, ['mention', 'target']).map((r) => r.kind), ['target', 'mention']);
  assert.equal(dismissalLabel(rows[0]), 'fate foulers');
  assert.equal(dismissalLabel(rows[1]), 'A → Aitrip (every mention in this note)');
  assert.equal(dismissalLabel(rows[2]), 'Never suggest links to Hozon');
});

test('Story tells apart "no folders configured" from "folders with no scenes"', () => {
  assert.deepEqual(storyEmptyState([]), { configured: false, folders: [] });
  assert.deepEqual(storyEmptyState(undefined), { configured: false, folders: [] });
  assert.deepEqual(storyEmptyState(['Story']), { configured: true, folders: ['Story'] });
});

test('a note that names an entry several times lists one row: its first mention', () => {
  const rows = [
    mention({ start: 3, end: 9 }),
    mention({ start: 20, end: 26 }),
    mention({ start: 40, end: 46 }),
    mention({ start: 50, end: 56, text: 'aitrip', exact_case: false, actionable: false }),
    mention({ source_path: 'B.md' }),
  ];
  const collapsed = collapseMentions(rows);
  assert.equal(collapsed.length, 3, 'A.md linkable, A.md lowercase, B.md');
  assert.deepEqual(collapsed.map((row) => [row.source_path, row.start, row.more]),
    [['A.md', 3, 2], ['A.md', 50, 0], ['B.md', 3, 0]]);
  assert.equal(moreLabel(collapsed[0]), '+2 more in this note');
  assert.equal(moreLabel(collapsed[1]), '');
  // Dismissing a note hides both of its rows and all four of its mentions.
  assert.deepEqual([collapsed[0].pairRows, collapsed[0].pairActionable, collapsed[0].pairOccurrences], [2, 1, 4]);
  assert.deepEqual([collapsed[2].pairRows, collapsed[2].pairActionable, collapsed[2].pairOccurrences], [1, 1, 1]);
  assert.deepEqual(mentionTotals(rows), { rows: 3, actionable: 2, occurrences: 5 });
  assert.equal(rows[0].more, undefined, 'the server rows are not modified');
  const groups = groupMentions(rows, [{ target_path: 'Places/Aitrip.md', notes: 2, mentions: 4 }]);
  assert.equal(groups[0].actionable.length, 2);
  assert.equal(groups[0].occurrences, 5);
  assert.equal(groupHeading(groups[0]), 'Aitrip — named in 2 notes without a link');
});

test('mentions dismissed on this page stay out of a repaint', () => {
  const rows = [mention({}), mention({ source_path: 'B.md' }), mention({ target_path: 'Z.md' })];
  const dismissed = { pairs: new Set(['A.md|Places/Aitrip.md']), targets: new Set(['Z.md']) };
  assert.deepEqual(visibleMentions(rows, dismissed).map((row) => row.source_path), ['B.md']);
  assert.equal(visibleMentions(rows).length, 3);
});

test('dismissals and their effect are told apart', () => {
  assert.equal(dismissalText(1, 29, 'mention'), '1 dismissed (hides 29 mentions)');
  assert.equal(dismissalText(2, 1, 'mention'), '2 dismissed (hides 1 mention)');
  assert.equal(dismissalText(3, 3, 'mention'), '3 dismissed');
  assert.equal(dismissalText(1, null, 'mention'), '1 dismissed');
  assert.equal(dismissalText(1, 5), '1 dismissed');
});

test('a rolled entry is linked by the server\'s link, labelled with its title', () => {
  assert.equal(rollLink({ path: 'Flora and Fauna/Forest-Jungle/Hozon/Honestree.md', title: 'Honestree', link: 'Honestree' }),
    '[[Honestree]]');
  assert.equal(rollLink({ path: 'A/Twin.md', title: 'Twin', link: 'A/Twin' }), '[[A/Twin|Twin]]');
  assert.equal(rollLink({ path: 'A/Twin.md', title: 'Twin' }), '[[A/Twin|Twin]]', 'older servers send no link');
  const start = rollStart({ facet: 'Uses', words: [], entry: {
    path: 'Flora and Fauna/Forest-Jungle/Hozon/Honestree.md', title: 'Honestree', link: 'Honestree',
    from_targets: [] } });
  assert.equal(start.body, 'Relates to [[Honestree]]\n\n## Uses\n\n');
});
