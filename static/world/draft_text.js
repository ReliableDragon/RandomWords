// Pure helpers for an unsaved new entry. Nothing here touches the page.
//
// A new draft is plain text, header lines included: the From:/Origin: lines,
// tags and template headings live in the textarea like any other words, so
// what the writer sees is exactly what is saved.

const HEADER_LINE = /^(From|Origin|Source|Themes):\s*(.*)$/i;
const TAG_ONLY_LINE = /^#[\w-]+(?:\s+#[\w-]+)*\s*$/;
const WIKILINK = /\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]/g;

// -- Prefill to text -------------------------------------------------------

// [{word, gloss}] -> "rainseed (a rain-made lantern), loam"
export function seedsText(seeds) {
  return (seeds || []).map((seed) => {
    const word = typeof seed === 'string' ? seed : seed.word;
    const gloss = typeof seed === 'string' ? '' : seed.gloss;
    return gloss ? word + ' (' + gloss + ')' : word;
  }).join(', ');
}

// ['flora', '#loaming'] -> "#flora #loaming"
export function tagsLine(tags) {
  return (tags || []).map((tag) => '#' + String(tag).replace(/^#/, '')).filter((tag) => tag.length > 1).join(' ');
}

// The words of `extra` that `seeds` does not already hold, as seed objects.
export function mergeSeeds(seeds, extra) {
  const merged = (seeds || []).map((seed) => (typeof seed === 'string' ? { word: seed, gloss: '' } : seed));
  (extra || []).forEach((word) => {
    if (!merged.some((seed) => seed.word === word)) merged.push({ word, gloss: '' });
  });
  return merged;
}

// The first text of a draft: header lines, then a blank line for the writer
// to start under, then any prefilled body.
//   fromLinks  ['[[Marsh]]', ...]   seeds  [{word, gloss}]   tags  ['flora']
export function buildDraftText(parts) {
  const lines = [];
  if ((parts.fromLinks || []).length) lines.push('From: ' + parts.fromLinks.join(' '));
  if ((parts.seeds || []).length) lines.push('Origin: ' + seedsText(parts.seeds));
  const tags = tagsLine(parts.tags);
  if (tags) lines.push(tags);
  const body = parts.body || '';
  if (!lines.length) return body;
  return lines.join('\n') + '\n\n' + body;
}

// The text a prefill opens a draft with. `links` are the From [[links]]
// already resolved for its fromTargets; `kept` the words on the bench, all of
// which go on the Origin: line (the writer deletes the ones they do not want).
export function prefillText(prefill, links, kept) {
  return buildDraftText({
    fromLinks: links, seeds: mergeSeeds(prefill.seeds, kept), tags: prefill.tags, body: prefill.body,
  });
}

// -- The header block ------------------------------------------------------

function splitLines(text) {
  const lines = [];
  let offset = 0;
  text.split('\n').forEach((line) => {
    // A CRLF text keeps its \r out of the line, so the header patterns match.
    lines.push({ text: line.replace(/\r$/, ''), start: offset });
    offset += line.length + 1;
  });
  return lines;
}

// Offset where the header block ends: after any frontmatter, the From:,
// Origin:, Source: and Themes: lines, and tag-only lines among them.
export function headerEnd(text) {
  const lines = splitLines(text);
  let i = 0;
  if (lines.length && lines[0].text.replace(/^﻿/, '').trim() === '---') {
    const close = lines.findIndex((line, at) => at > 0 && line.text.trim() === '---');
    if (close > 0) i = close + 1;
  }
  while (i < lines.length && (HEADER_LINE.test(lines[i].text) || TAG_ONLY_LINE.test(lines[i].text))) i++;
  if (i >= lines.length) return text.length;
  return lines[i].start;
}

export function bodyIsEmpty(text) {
  return text.slice(headerEnd(text)).trim() === '';
}

// -- From links ------------------------------------------------------------

// The [[wikilinks]] on the From: line, with their offsets in `text`.
// Each is {raw, target, label, display, start, end}.
export function fromLinks(text) {
  const found = [];
  const end = headerEnd(text);
  splitLines(text.slice(0, end)).forEach((line) => {
    const match = line.text.match(/^From:\s*/i);
    if (!match) return;
    const base = line.start + match[0].length;
    const rest = line.text.slice(match[0].length);
    WIKILINK.lastIndex = 0;
    let hit;
    while ((hit = WIKILINK.exec(rest))) {
      const target = hit[1].trim();
      const label = hit[2] ? hit[2].trim() : '';
      found.push({
        raw: hit[0], target, label,
        display: label || target.split('/').pop().replace(/\.md$/i, ''),
        start: base + hit.index, end: base + hit.index + hit[0].length,
      });
    }
  });
  return found;
}

// True when two link targets name the same entry: equal paths, or a bare
// title against a path that ends in it.
export function sameTarget(a, b) {
  const x = a.replace(/\.md$/i, '').toLocaleLowerCase();
  const y = b.replace(/\.md$/i, '').toLocaleLowerCase();
  if (x === y) return true;
  return x.split('/').pop() === y.split('/').pop() && (x.indexOf('/') < 0 || y.indexOf('/') < 0);
}

// The target inside "[[Target|label]]".
export function linkTargetOf(link) {
  const match = String(link).match(/^\[\[([^\]|]+)/);
  return match ? match[1].trim() : '';
}

export function hasFromLink(text, target) {
  return fromLinks(text).some((link) => sameTarget(link.target, target));
}

// Offset just past any frontmatter, where the header lines begin. Frontmatter
// whose closing fence is the last line (no newline after it) ends the text.
function headerStartOffset(text) {
  const lines = splitLines(text);
  if (!lines.length || lines[0].text.replace(/^\ufeff/, '').trim() !== '---') return 0;
  const close = lines.findIndex((line, at) => at > 0 && line.text.trim() === '---');
  if (close < 0) return 0;
  return close + 1 < lines.length ? lines[close + 1].start : text.length;
}

// Adds a [[link]] to the From: line, wherever it sits in the header block
// (after tag-only lines too) and whether or not it already holds links. A
// draft with no From: line gets one at the top of the header lines, ahead of
// Origin:. Returns the new text, or null when the From: line lives in
// frontmatter and must be edited by hand.
export function addFromLink(text, link) {
  const at = headerStartOffset(text);
  if (/^From:/im.test(text.slice(0, at))) return null;
  const eol = text.indexOf('\r\n') >= 0 ? '\r\n' : '\n';
  const end = headerEnd(text);
  const existing = splitLines(text.slice(0, end)).find((line) => line.start >= at && /^From:/i.test(line.text));
  if (existing) {
    const value = existing.text.replace(/\s+$/, '');
    return text.slice(0, existing.start) + value + ' ' + link + text.slice(existing.start + existing.text.length);
  }
  const rest = text.slice(at);
  const first = rest.split('\n')[0].replace(/\r$/, '');
  const abuts = first.trim() !== '' && !HEADER_LINE.test(first) && !TAG_ONLY_LINE.test(first);
  // Frontmatter that ends the text without a newline needs one before the line.
  const lead = at > 0 && at === text.length && !/\n$/.test(text) ? eol : '';
  return text.slice(0, at) + lead + 'From: ' + link + eol + (abuts ? eol : '') + rest;
}

// Removes one From link, and the whole line once it holds no links.
// Returns the new text (unchanged when the link is not there).
export function removeFromLink(text, target) {
  const link = fromLinks(text).find((item) => sameTarget(item.target, target));
  if (!link) return text;
  const lineStart = text.lastIndexOf('\n', link.start - 1) + 1;
  let lineEnd = text.indexOf('\n', link.end);
  if (lineEnd < 0) lineEnd = text.length;
  const line = text.slice(lineStart, lineEnd);
  const remaining = line.slice(0, link.start - lineStart) + line.slice(link.end - lineStart);
  if (/^From:\s*$/i.test(remaining.trim())) {
    const rest = text.slice(Math.min(text.length, lineEnd + 1));
    // The gap that followed the header goes with it when nothing is above.
    return text.slice(0, lineStart) + (lineStart === 0 ? rest.replace(/^\n+/, '') : rest);
  }
  return text.slice(0, lineStart) + remaining.replace(/\s{2,}/g, ' ').replace(/\s+$/, '') + text.slice(lineEnd);
}

// The names the From: line holds, for showing in the placement bar.
export function fromNames(text) {
  return fromLinks(text).map((link) => link.display);
}

// -- Templates -------------------------------------------------------------

const cleanTemplate = (value) => String(value || '').replace(/\r\n?/g, '\n').replace(/\s+$/, '');

export function templateLabel(path) {
  return String(path || '').replace(/^Templates\//, '').replace(/\.md$/i, '');
}

// Puts a template's headings under the header lines, but only while the
// writer has written nothing there. A body that is still just the template
// this draft inserted earlier is swapped for the new one.
// Returns {text, placed, start}: placed is true when the headings went in,
// and start is where they begin.
export function placeTemplate(text, templateText, previousTemplate) {
  const template = cleanTemplate(templateText);
  if (!template) return { text, placed: false, start: -1 };
  const end = headerEnd(text);
  const body = text.slice(end).trim();
  const previous = cleanTemplate(previousTemplate);
  if (body && !(previous && body === previous.trim())) return { text, placed: false, start: -1 };
  let head = text.slice(0, end);
  if (head && !head.endsWith('\n')) head += '\n';
  if (head.trim() && !head.endsWith('\n\n')) head += '\n';
  return { text: head + template + '\n\n', placed: true, start: head.length };
}

// The template's headings after everything the writer has written.
export function appendTemplate(text, templateText) {
  const template = cleanTemplate(templateText);
  if (!template) return text;
  const body = text.replace(/\s+$/, '');
  return (body ? body + '\n\n' : '') + template + '\n';
}

// -- Naming and placing ----------------------------------------------------

// A title the server would refuse, or ''.
export function titleProblem(title) {
  const value = String(title || '').trim();
  if (!value) return 'Give this entry a title to save it.';
  if (value === '.' || value === '..' || value.charAt(0) === '.' || /[\\/]/.test(value)) {
    return 'A title can\'t contain / or \\ or start with a dot, because it becomes the file name.';
  }
  return '';
}

// Where Nearby should think the draft lives. A draft with no folder yet is
// Draft.md, which the server also falls back to.
export function prospectivePath(draft) {
  if (!draft || draft.folder == null) return 'Draft.md';
  const name = String(draft.title || '').trim() || 'Draft';
  return (draft.folder ? draft.folder + '/' : '') + name + '.md';
}

// What blocks saving: {title, folder} messages, empty strings when fine.
export function draftIssues(draft) {
  return {
    title: titleProblem(draft.title),
    folder: draft.folder == null ? 'Choose a folder for this entry to save it.' : '',
  };
}

// True once there is something worth keeping: words or a title, beyond what
// the draft was opened with.
export function draftHasContent(text, title, initialText) {
  const written = String(text || '').trim() !== '' && text !== initialText;
  return written || String(title || '').trim() !== '';
}

// The labels the placement bar shows. `folder` is null until one is chosen.
export function placementParts(draft, text) {
  const names = fromNames(text || '');
  const folder = draft.folder == null ? '' : (draft.folder || 'Vault root');
  const template = draft.template ? templateLabel(draft.template) : '';
  const lastFolder = folder ? folder.split('/').pop() : '';
  return {
    folder, names, template,
    // The one line a phone shows.
    short: names[0] || lastFolder || 'Choose where it lives',
  };
}

// -- Editing the text in place ---------------------------------------------

// The smallest {start, end, replacement} turning `before` into `after`.
export function diffSpan(before, after) {
  let start = 0;
  const limit = Math.min(before.length, after.length);
  while (start < limit && before.charAt(start) === after.charAt(start)) start++;
  let tail = 0;
  while (tail < limit - start
    && before.charAt(before.length - 1 - tail) === after.charAt(after.length - 1 - tail)) tail++;
  return { start, end: before.length - tail, replacement: after.slice(start, after.length - tail) };
}

// Where a caret goes after text[start, end) is replaced by `length` characters:
// carets before the edit stay, carets after it move with it, and carets in or
// at the edit land after it, as if the writer had typed it.
export function adjustCaret(caret, start, end, length) {
  if (caret < start) return caret;
  if (caret >= end) return caret + length - (end - start);
  return start + length;
}

export function newDraftId(now, random) {
  return 'd' + now.toString(36) + '-' + Math.floor(random * 1e6).toString(36);
}
