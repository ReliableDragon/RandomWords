import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildMarks, driftAt, driftIndex, findDriftRanges, findWikilinks, linkIsCurrent, linkKey, linkStatusMap,
  linkSummary, matchCase, problemLinks, qualifiedLink, segments,
} from '../static/world/editor_marks.js';

const links = [
  { target: 'Glow', status: 'ambiguous', candidates: ['A/Glow.md', 'B/Glow.md'] },
  { target: 'Nowhere', status: 'unresolved', candidates: [] },
  { target: 'Harbor', status: 'resolved', resolved_path: 'Places/Harbor.md', candidates: [] },
];

test('wikilinks are split into target, heading and label like the server does', () => {
  const found = findWikilinks('See [[Places/Harbor#Docks|the docks]] and [[Ada]].');
  assert.deepEqual(found.map((l) => [l.target, l.heading, l.display]), [
    ['Places/Harbor', 'Docks', 'the docks'], ['Ada', '', ''],
  ]);
  assert.equal(found[0].raw, '[[Places/Harbor#Docks|the docks]]');
});

test('only unresolved and ambiguous links known to the server are problems', () => {
  const text = 'A [[Glow]] then [[nowhere|out there]], [[Harbor]] and a new [[Typed Later]].';
  const problems = problemLinks(text, linkStatusMap(links));
  assert.deepEqual(problems.map((p) => [p.target, p.status, p.line]), [
    ['Glow', 'ambiguous', 1], ['nowhere', 'unresolved', 1],
  ]);
  assert.deepEqual(problems[0].candidates, ['A/Glow.md', 'B/Glow.md']);
  assert.equal(linkSummary(problems), '1 unresolved · 1 ambiguous');
  assert.equal(linkSummary([]), '');
});

test('line numbers count newlines before the link', () => {
  const problems = problemLinks('one\ntwo\n[[Nowhere]]', linkStatusMap(links));
  assert.equal(problems[0].line, 3);
});

test('an ambiguous link is pinned to the chosen path and keeps what the writer saw', () => {
  const [problem] = problemLinks('a [[Glow]] b', linkStatusMap(links));
  assert.equal(qualifiedLink(problem, 'A/Glow.md'), '[[A/Glow]]');
  const labelled = { target: 'Glow', display: 'the glow', heading: 'Bright' };
  assert.equal(qualifiedLink(labelled, 'B/Glow Fox.md'), '[[B/Glow Fox#Bright|the glow]]');
  assert.equal(qualifiedLink({ target: 'Foxfire', display: '', heading: '' }, 'B/Glow Fox.md'), '[[B/Glow Fox|Foxfire]]');
});

test('a link edit is refused when the span no longer holds the listed link', () => {
  const text = 'a [[Glow]] b';
  const [problem] = problemLinks(text, linkStatusMap(links));
  assert.equal(linkIsCurrent(text, problem), true);
  assert.equal(linkIsCurrent('xx' + text, problem), false);
});

test('link keys ignore case, spacing and backslashes', () => {
  assert.equal(linkKey('  Places\\Harbor '), 'places/harbor');
});

test('casing carries over to a replacement', () => {
  assert.equal(matchCase('alzerati', 'alzarati'), 'alzarati');
  assert.equal(matchCase('Alzerati', 'alzarati'), 'Alzarati');
  assert.equal(matchCase('ALZERATI', 'alzarati'), 'ALZARATI');
});

const drift = driftIndex([
  { from: 'alzerati', to: 'alzarati' }, { from: 'alzerati', to: 'other' }, { from: 'foxfyre', to: 'foxfire' },
]);

test('the rarer spelling is found with its casing, plural and possessive', () => {
  const text = 'The Alzerati sing. Two alzeratis; the alzerati’s hall. Alzarati is fine.';
  const ranges = findDriftRanges(text, drift);
  assert.deepEqual(ranges.map((r) => [text.slice(r.start, r.end), r.replacement]), [
    ['Alzerati', 'Alzarati'], ['alzeratis', 'alzaratis'], ['alzerati’s', 'alzarati’s'],
  ]);
  assert.equal(ranges[0].to, 'alzarati', 'the first pair for a spelling wins');
});

test('drift inside a wikilink is not offered', () => {
  const text = 'See [[Alzerati]] and alzerati.';
  const ranges = findDriftRanges(text, drift);
  assert.equal(ranges.length, 1);
  assert.equal(text.slice(ranges[0].start, ranges[0].end), 'alzerati');
  assert.equal(ranges[0].start, text.lastIndexOf('alzerati'));
});

test('marks combine links and drift in order and never overlap', () => {
  const text = 'foxfyre near [[Glow]] and [[Nowhere]].';
  const marks = buildMarks(text, linkStatusMap(links), drift);
  assert.deepEqual(marks.map((m) => m.kind), ['drift', 'link-ambiguous', 'link-unresolved']);
  const pieces = segments(text, marks);
  assert.equal(pieces.map((p) => p.text).join(''), text);
  assert.deepEqual(pieces.filter((p) => p.mark).map((p) => p.text), ['foxfyre', '[[Glow]]', '[[Nowhere]]']);
});

test('segments of unmarked text are one piece; a trailing newline survives', () => {
  assert.deepEqual(segments('plain\n', []), [{ text: 'plain\n', mark: null }]);
});

test('the hint finds the drift range holding the caret, edges included', () => {
  const text = 'the alzerati sing';
  const marks = buildMarks(text, new Map(), drift);
  assert.equal(driftAt(marks, 4).word, 'alzerati');
  assert.equal(driftAt(marks, 12).word, 'alzerati');
  assert.equal(driftAt(marks, 13), null);
  assert.equal(driftAt(marks, 2), null);
});

test('no drift data means no marks', () => {
  assert.deepEqual(findDriftRanges('anything', new Map()), []);
  assert.deepEqual(buildMarks('plain', new Map(), new Map()), []);
});
