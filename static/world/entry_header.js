// Adds From / Origin / Themes lines to an entry's recognized header block.
// Pure: takes the text, returns the new text.

const HEADER_LINE = /^(From|Origin|Source|Themes):\s*(.*)$/i;
const WIKILINKS = /^\[\[[^\]]+\]\](?:\s+\[\[[^\]]+\]\])*$/;
const LABELS = { from: 'From', origin: 'Origin', themes: 'Themes' };

function fail(error) {
  return { ok: false, error };
}

// A From value must be wikilinks or a canonical .md path.
function normalizeFrom(value) {
  if (WIKILINKS.test(value)) return value;
  if (/^[^\s]+\.md$/i.test(value)) return '[[' + value.replace(/\.md$/i, '') + ']]';
  return null;
}

function closingFence(lines) {
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === '---') return i;
  }
  return -1;
}

function yamlKeys(lines) {
  return lines.map((line) => {
    const match = line.match(/^([A-Za-z_][\w-]*):/);
    return match && match[1].toLowerCase();
  });
}

function sameField(field, name) {
  const lower = name.toLowerCase();
  return field === 'origin' ? (lower === 'origin' || lower === 'source') : lower === field;
}

// Index of the existing line for `field` inside lines[start, end), or -1.
function findLine(lines, start, end, field) {
  for (let i = start; i < end; i++) {
    const match = lines[i].match(HEADER_LINE);
    if (match && sameField(field, match[1])) return i;
  }
  return -1;
}

// Where the header block begins: after frontmatter when there is any.
function headerStart(lines, field, label) {
  if (!lines.length || lines[0].replace(/^﻿/, '').trim() !== '---') return { start: 0 };
  const close = closingFence(lines);
  if (close < 0) {
    return { error: 'The frontmatter is not closed, so a structured header cannot be placed safely. Use a raw Markdown line instead.' };
  }
  const wanted = field === 'origin' ? ['origin', 'source'] : [field];
  if (yamlKeys(lines.slice(1, close)).some((key) => wanted.indexOf(key) >= 0)) {
    return { error: label + ' is set in YAML frontmatter. Edit that raw field directly so its formatting is preserved.' };
  }
  return { start: close + 1 };
}

// Returns {ok: true, text, caret} or {ok: false, error}. `caret` is the
// offset at the end of the header line that was added or extended.
export function insertHeader(text, field, rawValue) {
  const label = LABELS[field];
  let value = rawValue;
  if (field === 'from') {
    value = normalizeFrom(rawValue);
    if (value === null) {
      return fail('From needs a canonical .md path or a wikilink. Use the From target selector when creating an entry.');
    }
  }
  const lines = text.split('\n');
  const begin = headerStart(lines, field, label);
  if (begin.error) return fail(begin.error);

  let end = begin.start;
  while (end < lines.length && HEADER_LINE.test(lines[end])) end++;

  let index = findLine(lines, begin.start, end, field);
  if (index >= 0) {
    const match = lines[index].match(HEADER_LINE);
    const existing = match[2].trim();
    const separator = field === 'themes' ? ', ' : ' ';
    lines[index] = match[1] + ': ' + (existing ? existing + separator : '') + value;
  } else {
    index = end;
    lines.splice(end, 0, label + ': ' + value);
  }
  const lineStart = lines.slice(0, index).join('\n').length + (index ? 1 : 0);
  return { ok: true, text: lines.join('\n'), caret: lineStart + lines[index].length };
}
