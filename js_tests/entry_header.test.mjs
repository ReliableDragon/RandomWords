import test from 'node:test';
import assert from 'node:assert/strict';

import { insertHeader } from '../static/world/entry_header.js';

function apply(text, field, value) {
  const result = insertHeader(text, field, value);
  assert.equal(result.ok, true, result.error);
  return result;
}

test('a first header goes at the top of a plain note', () => {
  const result = apply('Body text.', 'themes', 'loss');
  assert.equal(result.text, 'Themes: loss\nBody text.');
  assert.equal(result.caret, 'Themes: loss'.length);
});

test('a new header joins the existing header block', () => {
  const text = 'From: [[Harbor]]\nThemes: loss\n\nBody.';
  const result = apply(text, 'origin', 'rainseed (a lantern)');
  assert.equal(result.text, 'From: [[Harbor]]\nThemes: loss\nOrigin: rainseed (a lantern)\n\nBody.');
  assert.equal(result.text.slice(0, result.caret).split('\n').pop(), 'Origin: rainseed (a lantern)');
});

test('themes extend the existing line with a comma', () => {
  const result = apply('Themes: loss\n\nBody.', 'themes', 'rain');
  assert.equal(result.text, 'Themes: loss, rain\n\nBody.');
});

test('origin extends an existing Source line and keeps its label', () => {
  const result = apply('Source: loam\n\nBody.', 'origin', 'rain');
  assert.equal(result.text, 'Source: loam rain\n\nBody.');
});

test('from accepts a canonical .md path and writes a wikilink', () => {
  assert.equal(apply('Body.', 'from', 'Places/Harbor.md').text, 'From: [[Places/Harbor]]\nBody.');
});

test('from accepts wikilinks as they are', () => {
  assert.equal(apply('Body.', 'from', '[[A]] [[B]]').text, 'From: [[A]] [[B]]\nBody.');
});

test('from rejects free text', () => {
  const result = insertHeader('Body.', 'from', 'the harbor');
  assert.equal(result.ok, false);
  assert.match(result.error, /canonical \.md path or a wikilink/);
});

test('headers go after frontmatter, which is preserved', () => {
  const text = '---\ntitle: X\n---\nBody.';
  assert.equal(apply(text, 'themes', 'loss').text, '---\ntitle: X\n---\nThemes: loss\nBody.');
});

test('a field set in frontmatter is not duplicated', () => {
  const result = insertHeader('---\nthemes: a\n---\nBody.', 'themes', 'b');
  assert.equal(result.ok, false);
  assert.match(result.error, /YAML frontmatter/);
  assert.equal(insertHeader('---\nsource: a\n---\nBody.', 'origin', 'b').ok, false);
});

test('unclosed frontmatter is refused', () => {
  const result = insertHeader('---\ntitle: X\nBody.', 'themes', 'b');
  assert.equal(result.ok, false);
  assert.match(result.error, /not closed/);
});

test('a byte order mark before the fence still counts as frontmatter', () => {
  const result = apply('﻿---\na: b\n---\nBody.', 'themes', 'x');
  assert.equal(result.text, '﻿---\na: b\n---\nThemes: x\nBody.');
});
