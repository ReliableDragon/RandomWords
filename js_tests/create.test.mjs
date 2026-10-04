// The pure side of write-first drafts: how a prefill becomes text, the header
// block, From links, template placement and what blocks saving.

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  addFromLink, adjustCaret, appendTemplate, bodyIsEmpty, buildDraftText, diffSpan, draftHasContent, draftIssues,
  fromLinks, hasFromLink, headerEnd, mergeSeeds, placeTemplate, placementParts, prefillText, prospectivePath,
  removeFromLink, sameTarget, seedsText, tagsLine, templateLabel, titleProblem,
} from '../static/world/draft_text.js';
import { placesFirst } from '../static/world/placement.js';

// -- Prefill to text ---------------------------------------------------------

test('seeds become one Origin: line, glosses included', () => {
  assert.equal(seedsText([{ word: 'rainseed', gloss: 'a rain-made lantern' }, { word: 'loam' }, 'moss']),
    'rainseed (a rain-made lantern), loam, moss');
  assert.equal(seedsText(undefined), '');
});

test('tags become one #tag line and lose a doubled #', () => {
  assert.equal(tagsLine(['flora', '#loaming']), '#flora #loaming');
  assert.equal(tagsLine(undefined), '');
  assert.equal(tagsLine(['#']), '');
});

test('kept words are all added to the seeds, once each', () => {
  assert.deepEqual(mergeSeeds([{ word: 'loam', gloss: 'soil' }], ['loam', 'reed']),
    [{ word: 'loam', gloss: 'soil' }, { word: 'reed', gloss: '' }]);
  assert.deepEqual(mergeSeeds(undefined, []), []);
});

test('with no header lines the draft is just the body, with them a blank line follows', () => {
  assert.equal(buildDraftText({}), '');
  assert.equal(buildDraftText({ body: 'Relates to [[X]]\n\n' }), 'Relates to [[X]]\n\n');
  assert.equal(buildDraftText({ fromLinks: ['[[Marsh]]'], seeds: [{ word: 'loam' }], tags: ['flora'] }),
    'From: [[Marsh]]\nOrigin: loam\n#flora\n\n');
  assert.equal(buildDraftText({ fromLinks: ['[[Marsh]]'], body: 'First.' }), 'From: [[Marsh]]\n\nFirst.');
});

test('"Start entry from kept words" puts every kept word on an Origin: line', () => {
  assert.equal(prefillText({}, [], ['uncouth', 'word-painter']), 'Origin: uncouth, word-painter\n\n');
});

test('a Coverage cell becomes a From: line, with kept words on Origin:', () => {
  assert.equal(prefillText({ folder: 'Flora', fromTargets: ['Biomes/Marsh.md'] }, ['[[Marsh]]'], ['moss']),
    'From: [[Marsh]]\nOrigin: moss\n\n');
});

test('a roll keeps its words, its From targets and its first line', () => {
  const prefill = {
    seeds: [{ word: 'watchtower', gloss: '' }, { word: 'verd', gloss: '' }],
    body: 'Relates to [[Deep Watchers]]\n\n## Motivations\n\n',
  };
  assert.equal(prefillText(prefill, ['[[L]]'], []),
    'From: [[L]]\nOrigin: watchtower, verd\n\nRelates to [[Deep Watchers]]\n\n## Motivations\n\n');
});

test('a backlog idea, an unresolved link and an unlinked name only carry a title', () => {
  assert.equal(prefillText({ title: 'Isolated Deep-Sea Island', idea: {} }, [], []), '');
  assert.equal(prefillText({ title: 'Harbor', folder: 'Places' }, ['[[Marsh]]'], []), 'From: [[Marsh]]\n\n');
});

// -- The header block --------------------------------------------------------

test('the header block is the From/Origin/Themes lines and tag-only lines under any frontmatter', () => {
  const text = 'From: [[A]]\nOrigin: x\n#flora #loam\n\nBody here';
  assert.equal(text.slice(headerEnd(text)), '\nBody here');
  const framed = '---\naliases: Q\n---\nFrom: [[A]]\n\nBody';
  assert.equal(framed.slice(headerEnd(framed)), '\nBody');
  assert.equal(headerEnd('Just prose'), 0);
  assert.equal(headerEnd('Origin: only'), 'Origin: only'.length);
});

test('a body counts as empty while only whitespace follows the header', () => {
  assert.equal(bodyIsEmpty('From: [[A]]\n\n'), true);
  assert.equal(bodyIsEmpty(''), true);
  assert.equal(bodyIsEmpty('From: [[A]]\n\nWords'), false);
});

// -- From links --------------------------------------------------------------

test('From links are read with their offsets and display names', () => {
  const text = 'From: [[Loaming Country]] [[Places/Harbor|the harbor]]\n\nBody [[Not From]]';
  const links = fromLinks(text);
  assert.deepEqual(links.map((l) => [l.target, l.display]),
    [['Loaming Country', 'Loaming Country'], ['Places/Harbor', 'the harbor']]);
  assert.equal(text.slice(links[0].start, links[0].end), '[[Loaming Country]]');
  assert.equal(hasFromLink(text, 'Loaming Country.md'), true);
  assert.equal(hasFromLink(text, 'Not From'), false);
});

test('targets match by path, or by a bare title against a path', () => {
  assert.equal(sameTarget('Locations/Marsh.md', 'locations/marsh'), true);
  assert.equal(sameTarget('Marsh', 'Locations/Biomes/Marsh.md'), true);
  assert.equal(sameTarget('Flora/Marsh', 'Locations/Marsh'), false);
});

test('a From link goes in ahead of Origin:, extends an existing From: line, and never doubles', () => {
  assert.equal(addFromLink('Origin: loam\n\nBody', '[[Marsh]]'), 'From: [[Marsh]]\nOrigin: loam\n\nBody');
  assert.equal(addFromLink('From: [[A]]\n\nBody', '[[B]]'), 'From: [[A]] [[B]]\n\nBody');
  assert.equal(addFromLink('Prose first', '[[Marsh]]'), 'From: [[Marsh]]\n\nProse first');
  assert.equal(addFromLink('', '[[Marsh]]'), 'From: [[Marsh]]\n');
  assert.equal(addFromLink('---\nFrom: x\n---\nBody', '[[Marsh]]'), null, 'a From in frontmatter is left to the writer');
});

test('a From link goes in under frontmatter, not above it', () => {
  assert.equal(addFromLink('---\naliases: Q\n---\nBody', '[[Marsh]]'), '---\naliases: Q\n---\nFrom: [[Marsh]]\n\nBody');
});

test('a From: line without links is extended, not repeated', () => {
  assert.equal(addFromLink('From: Loaming Country\n\nBody', '[[Marsh]]'), 'From: Loaming Country [[Marsh]]\n\nBody');
  assert.equal(addFromLink('From:\n\nBody', '[[Marsh]]'), 'From: [[Marsh]]\n\nBody');
});

test('a From: line after a tag-only line is extended, not duplicated', () => {
  assert.equal(addFromLink('#flora\nFrom: [[A]]\n\nBody', '[[B]]'), '#flora\nFrom: [[A]] [[B]]\n\nBody');
  assert.equal(addFromLink('#flora\nFrom: plain\nOrigin: loam\n\nBody', '[[B]]'),
    '#flora\nFrom: plain [[B]]\nOrigin: loam\n\nBody');
});

test('frontmatter that ends the text puts From: under the closing fence', () => {
  assert.equal(addFromLink('---\ntitle: x\n---', '[[Marsh]]'), '---\ntitle: x\n---\nFrom: [[Marsh]]\n');
  assert.equal(addFromLink('---\ntitle: x\n---\n', '[[Marsh]]'), '---\ntitle: x\n---\nFrom: [[Marsh]]\n');
  assert.equal(addFromLink('---\r\ntitle: x\r\n---', '[[Marsh]]'), '---\r\ntitle: x\r\n---\r\nFrom: [[Marsh]]\r\n');
});

test('CRLF drafts keep their line endings when a From link is added', () => {
  assert.equal(addFromLink('Origin: loam\r\n\r\nBody', '[[Marsh]]'), 'From: [[Marsh]]\r\nOrigin: loam\r\n\r\nBody');
  assert.equal(addFromLink('From: [[A]]\r\n\r\nBody', '[[B]]'), 'From: [[A]] [[B]]\r\n\r\nBody');
  assert.equal(addFromLink('#flora\r\nFrom: plain\r\n\r\nBody', '[[B]]'), '#flora\r\nFrom: plain [[B]]\r\n\r\nBody');
  assert.equal(addFromLink('Prose', '[[B]]'), 'From: [[B]]\n\nProse');
});

test('removing a From link keeps the others, and drops the line when it empties', () => {
  assert.equal(removeFromLink('From: [[A]] [[B]]\n\nBody', 'A'), 'From: [[B]]\n\nBody');
  assert.equal(removeFromLink('From: [[A]]\nOrigin: x\n\nBody', 'A'), 'Origin: x\n\nBody');
  assert.equal(removeFromLink('From: [[A]]\n\nBody', 'Nope'), 'From: [[A]]\n\nBody');
  assert.equal(removeFromLink('From: [[A]]\n\nBody', 'A'), 'Body', 'the gap goes with the only header line');
});

// -- Templates ---------------------------------------------------------------

const TEMPLATE = '## Description\n\n## Habitat\n';

test('a template goes under the header lines while nothing is written there', () => {
  const placed = placeTemplate('From: [[A]]\nOrigin: x\n\n', TEMPLATE, '');
  assert.equal(placed.placed, true);
  assert.equal(placed.text, 'From: [[A]]\nOrigin: x\n\n## Description\n\n## Habitat\n\n');
  assert.equal(placed.text.slice(placed.start, placed.start + 14), '## Description');
  assert.equal(placeTemplate('', TEMPLATE, '').text, '## Description\n\n## Habitat\n\n');
  assert.equal(placeTemplate('Origin: x', TEMPLATE, '').text, 'Origin: x\n\n## Description\n\n## Habitat\n\n');
});

test('a template never lands above the writer\'s text', () => {
  const written = 'From: [[A]]\n\nThe aurochult drifted.';
  const result = placeTemplate(written, TEMPLATE, '');
  assert.equal(result.placed, false);
  assert.equal(result.text, written);
  assert.equal(appendTemplate(written, TEMPLATE), 'From: [[A]]\n\nThe aurochult drifted.\n\n## Description\n\n## Habitat\n');
});

test('a body that is still just the earlier template is swapped for the new one', () => {
  const first = placeTemplate('From: [[A]]\n\n', TEMPLATE, '');
  const swapped = placeTemplate(first.text, '## Practices\n', TEMPLATE);
  assert.equal(swapped.placed, true);
  assert.equal(swapped.text, 'From: [[A]]\n\n## Practices\n\n');
  // Once the writer has added anything, it stays.
  const edited = first.text.replace('## Habitat', '## Habitat\nReeds.');
  assert.equal(placeTemplate(edited, '## Practices\n', TEMPLATE).placed, false);
});

test('an empty template changes nothing', () => {
  assert.equal(placeTemplate('Words', '  \n', '').placed, false);
  assert.equal(appendTemplate('Words', ''), 'Words');
});

test('template labels drop the folder and extension', () => {
  assert.equal(templateLabel('Templates/Creature Template.md'), 'Creature Template');
  assert.equal(templateLabel(''), '');
});

// -- Naming and placing -------------------------------------------------------

test('a title the server would refuse is caught first, with a reason', () => {
  assert.match(titleProblem(''), /title/);
  assert.match(titleProblem('  '), /title/);
  assert.match(titleProblem('a/b'), /file name/);
  assert.match(titleProblem('.hidden'), /file name/);
  assert.equal(titleProblem('Loaming Reed'), '');
});

test('save is blocked by a missing title or folder, and the vault root counts as a folder', () => {
  assert.deepEqual(draftIssues({ title: '', folder: null }),
    { title: 'Give this entry a title to save it.', folder: 'Choose a folder for this entry to save it.' });
  assert.deepEqual(draftIssues({ title: 'X', folder: '' }), { title: '', folder: '' });
});

test('Nearby reads a draft as Draft.md until it has a folder, then folder/Title.md', () => {
  assert.equal(prospectivePath({ title: 'Reed', folder: null }), 'Draft.md');
  assert.equal(prospectivePath({ title: '', folder: 'Places' }), 'Places/Draft.md');
  assert.equal(prospectivePath({ title: ' Reed ', folder: 'Places/Marsh' }), 'Places/Marsh/Reed.md');
  assert.equal(prospectivePath({ title: 'Reed', folder: '' }), 'Reed.md');
  assert.equal(prospectivePath(null), 'Draft.md');
});

test('a draft only counts as having something once the writer adds to what it opened with', () => {
  assert.equal(draftHasContent('Origin: a\n\n', '', 'Origin: a\n\n'), false);
  assert.equal(draftHasContent('Origin: a\n\nMore', '', 'Origin: a\n\n'), true);
  assert.equal(draftHasContent('', 'A title', ''), true);
  assert.equal(draftHasContent('  \n', '', ''), false);
});

test('the placement bar names the folder, the places and the template', () => {
  const text = 'From: [[Loaming Country]]\n\nBody';
  assert.deepEqual(placementParts({ folder: 'Flora and Fauna/Marsh', template: 'Templates/Creature Template.md' }, text),
    { folder: 'Flora and Fauna/Marsh', names: ['Loaming Country'], template: 'Creature Template', short: 'Loaming Country' });
  const bare = placementParts({ folder: null, template: '' }, 'No header');
  assert.equal(bare.short, 'Choose where it lives');
  assert.equal(bare.folder, '');
  assert.equal(placementParts({ folder: 'Places/Harbors', template: '' }, '').short, 'Harbors');
  assert.equal(placementParts({ folder: '', template: '' }, '').folder, 'Vault root');
});

test('places are listed before other entries in a place search', () => {
  const rows = [{ path: 'Flora/Reed.md' }, { path: 'Locations/Marsh.md' }, { path: 'Overview.md' }, { path: 'Locations/Harbor.md' }];
  assert.deepEqual(placesFirst(rows).map((r) => r.path),
    ['Locations/Marsh.md', 'Locations/Harbor.md', 'Flora/Reed.md', 'Overview.md']);
});

// -- Editing in place ---------------------------------------------------------

test('a small edit is found as the span that changed', () => {
  assert.deepEqual(diffSpan('abcdef', 'abXYef'), { start: 2, end: 4, replacement: 'XY' });
  assert.deepEqual(diffSpan('abc', 'abc'), { start: 3, end: 3, replacement: '' });
  assert.deepEqual(diffSpan('Body', 'From: [[A]]\n\nBody'), { start: 0, end: 0, replacement: 'From: [[A]]\n\n' });
});

test('the caret stays on the writer\'s words when something is added above or below them', () => {
  assert.equal(adjustCaret(10, 0, 0, 5), 15);
  assert.equal(adjustCaret(3, 5, 5, 5), 3);
  assert.equal(adjustCaret(0, 0, 0, 5), 5, 'a caret at an insertion lands after it, as if typed');
  assert.equal(adjustCaret(7, 5, 10, 2), 7, 'a caret inside the replaced span lands after the replacement');
  assert.equal(adjustCaret(12, 5, 10, 2), 9);
});
