import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createFromTarget, detectLineEnding, displayPath, entryLinkTarget, entryTitle, escapeHtml, exportFilename, folderParent,
  ideaSeedTitle, isPeoplePath, splitSeeds, textareaText, toDiskText,
} from '../static/world/text.js';

test('escapeHtml escapes markup and tolerates null', () => {
  assert.equal(escapeHtml('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  assert.equal(escapeHtml(null), '');
});

test('line endings are detected and restored', () => {
  assert.equal(detectLineEnding('a\r\nb'), '\r\n');
  assert.equal(detectLineEnding('a\rb'), '\r');
  assert.equal(detectLineEnding('a\nb'), '\n');
  assert.equal(detectLineEnding(undefined), '\n');
  assert.equal(textareaText('a\r\nb\rc\nd'), 'a\nb\nc\nd');
  assert.equal(toDiskText('a\nb', '\r\n'), 'a\r\nb');
  assert.equal(toDiskText('a\r\nb', '\n'), 'a\nb');
});

test('titles fall back from title to name to file name', () => {
  assert.equal(entryTitle({ title: 'T', name: 'N', path: 'x/P.md' }), 'T');
  assert.equal(entryTitle({ name: 'N', path: 'x/P.md' }), 'N');
  assert.equal(entryTitle({ path: 'x/P.md' }), 'P');
  assert.equal(displayPath('x/P.md'), 'x/P');
});

test('folderParent and isPeoplePath', () => {
  assert.equal(folderParent('A/B/C'), 'A/B');
  assert.equal(folderParent('A'), '');
  assert.equal(folderParent(''), '');
  assert.equal(isPeoplePath('People/Ada.md'), true);
  assert.equal(isPeoplePath('Places/Ada.md'), false);
});

test('seeds split on commas outside brackets', () => {
  assert.deepEqual(splitSeeds('rainseed (a rain-made lantern, dim), loam ,, '), [
    'rainseed (a rain-made lantern, dim)', 'loam',
  ]);
});

test('export names are made safe and end in .html', () => {
  assert.equal(exportFilename('My story: part 1'), 'My-story-part-1.html');
  assert.equal(exportFilename('story.htm'), 'story.htm');
  assert.equal(exportFilename('///', 'story'), 'story.html');
  assert.equal(exportFilename(undefined, undefined), 'story.html');
});

test('idea titles are the first four words without trailing punctuation', () => {
  assert.equal(ideaSeedTitle('  A city that grows toward the light.'), 'A city that grows');
  assert.equal(ideaSeedTitle('Short idea!'), 'Short idea');
  assert.equal(ideaSeedTitle(undefined), '');
});

test('preview links to entries are recognized, others are not', () => {
  const base = 'http://127.0.0.1:8000/world';
  assert.deepEqual(entryLinkTarget('world:People%2FAda.md', '/api/world', base), { path: 'People/Ada.md' });
  assert.deepEqual(entryLinkTarget('/api/world/entry?path=People%2FAda.md', '/api/world', base), { path: 'People/Ada.md' });
  assert.deepEqual(entryLinkTarget('/world/entry?path=A.md', '/api/world', base), { path: 'A.md' });
  assert.deepEqual(entryLinkTarget('/world/entry', '/api/world', base), { path: '' });
  assert.equal(entryLinkTarget('https://example.com/', '/api/world', base), null);
  assert.equal(entryLinkTarget('/api/world/entryway?path=x', '/api/world', base), null);
});

test('a configured API base is recognized for preview links', () => {
  assert.deepEqual(
    entryLinkTarget('/api/v1/worlds/abc/entry?path=A.md', '/api/v1/worlds/abc', 'https://example.test/w'),
    { path: 'A.md' });
});

test('an unresolved link target becomes a title with no slash, and the folder part a folder', () => {
  assert.deepEqual(createFromTarget('Nowhere'), { title: 'Nowhere' });
  assert.deepEqual(createFromTarget('Places/Harbor', { fromTargets: ['A.md'] }),
    { title: 'Harbor', folder: 'Places', fromTargets: ['A.md'] });
  assert.deepEqual(createFromTarget('Places/Coast/Harbor.md'), { title: 'Harbor', folder: 'Places/Coast' });
});
