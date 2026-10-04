// Pure helpers for marking problems in the draft: wikilinks that do not
// resolve, and spellings that drift from a more common one. Offsets are
// UTF-16 positions in the textarea text, so they can be used with slice().

const WIKILINK = /\[\[([^\]]+)\]\]/g;
const WORD = /[\p{L}\p{N}\p{M}]+(?:['’][\p{L}\p{N}\p{M}]+)*/gu;

export function linkKey(target) {
  return String(target || '').trim().replace(/\\/g, '/').normalize('NFC').toLowerCase();
}

// Every [[target|display]] in the text, split the way the server splits it.
export function findWikilinks(text) {
  const links = [];
  const pattern = new RegExp(WIKILINK.source, 'g');
  let match = pattern.exec(text);
  while (match) {
    const inner = match[1];
    const bar = inner.indexOf('|');
    const head = bar < 0 ? inner : inner.slice(0, bar);
    const hash = head.indexOf('#');
    links.push({
      start: match.index,
      end: match.index + match[0].length,
      raw: match[0],
      target: (hash < 0 ? head : head.slice(0, hash)).trim(),
      heading: hash < 0 ? '' : head.slice(hash + 1).trim(),
      display: bar < 0 ? '' : inner.slice(bar + 1).trim(),
    });
    match = pattern.exec(text);
  }
  return links;
}

// The server's view of the saved text: target key -> {status, candidates,
// resolved_path}. A target that appears twice has one resolution.
export function linkStatusMap(links) {
  const map = new Map();
  (links || []).forEach((link) => {
    const key = linkKey(link.target);
    if (key && !map.has(key)) {
      map.set(key, {
        status: link.status || (link.resolved_path ? 'resolved' : 'unresolved'),
        candidates: link.candidates || [],
        resolved_path: link.resolved_path || null,
      });
    }
  });
  return map;
}

// Wikilinks in the current text that the server could not resolve. Links it
// has not seen (typed since the last save) are left alone. `links` may carry
// the already-found wikilinks of `text`.
export function problemLinks(text, statusMap, links) {
  const problems = [];
  const counter = lineCounter(text);
  (links || findWikilinks(text)).forEach((link) => {
    const info = link.target && statusMap.get(linkKey(link.target));
    if (!info || info.status === 'resolved') return;
    problems.push(Object.assign({}, link, {
      status: info.status === 'ambiguous' ? 'ambiguous' : 'unresolved',
      candidates: info.candidates,
      line: counter(link.start),
    }));
  });
  return problems;
}

// A function giving the 1-based line of an offset. It is cheap for offsets
// asked in increasing order (one pass over the text in all), and correct for
// any order.
function lineCounter(text) {
  let at = 0;
  let line = 1;
  return (offset) => {
    if (offset < at) {
      at = 0;
      line = 1;
    }
    let next = text.indexOf('\n', at);
    while (next >= 0 && next < offset) {
      line += 1;
      at = next + 1;
      next = text.indexOf('\n', at);
    }
    return line;
  };
}

// "2 unresolved · 1 ambiguous", or '' when nothing is wrong.
export function linkSummary(problems) {
  const count = (status) => problems.filter((item) => item.status === status).length;
  return [[count('unresolved'), 'unresolved'], [count('ambiguous'), 'ambiguous']]
    .filter(([n]) => n > 0)
    .map(([n, label]) => n + ' ' + label)
    .join(' · ');
}

// The wikilink that pins an ambiguous link to one entry: the full path, with
// the text the writer saw kept as the label unless it is the title itself.
export function qualifiedLink(problem, candidatePath) {
  const path = String(candidatePath).replace(/\.md$/i, '');
  const title = path.split('/').pop();
  const shown = problem.display || problem.target;
  const heading = problem.heading ? '#' + problem.heading : '';
  return '[[' + path + heading + (shown !== title ? '|' + shown : '') + ']]';
}

// The current text at the link's span still is the link that was listed.
export function linkIsCurrent(text, problem) {
  return text.slice(problem.start, problem.end) === problem.raw;
}

// -- Spelling drift ---------------------------------------------------------

// Carries the casing of an occurrence over to its replacement.
export function matchCase(source, replacement) {
  const letters = source.replace(/[^\p{L}]/gu, '');
  const lower = letters.toLowerCase();
  if (letters && letters === letters.toUpperCase() && letters !== lower) return replacement.toUpperCase();
  if (letters && letters === lower && letters !== letters.toUpperCase()) return replacement.toLowerCase();
  const first = source.charAt(0);
  const rest = source.slice(1);
  if (first !== first.toLowerCase() && rest === rest.toLowerCase()) {
    return replacement.charAt(0).toUpperCase() + replacement.slice(1).toLowerCase();
  }
  return replacement;
}

// Lexicon drift rows -> lower-cased rarer spelling -> {from, to}. Rows come
// sorted by closeness, so the first pair for a spelling wins.
export function driftIndex(rows) {
  const index = new Map();
  (rows || []).forEach((row) => {
    const key = linkKey(row.from);
    if (key && row.to && !index.has(key)) index.set(key, { from: row.from, to: row.to });
  });
  return index;
}

// The pair for a token, allowing the possessive or plural the server allows.
function driftFor(token, index) {
  const folded = token.normalize('NFC').toLowerCase();
  if (index.has(folded)) return { pair: index.get(folded), stem: token, suffix: '' };
  const possessive = /['’]s$/.test(folded);
  if (possessive || (folded.endsWith('s') && folded.length > 1)) {
    const cut = possessive ? 2 : 1;
    const base = folded.slice(0, -cut);
    if (index.has(base)) {
      return { pair: index.get(base), stem: token.slice(0, -cut), suffix: token.slice(-cut) };
    }
  }
  return null;
}

// Where known drift spellings occur, outside wikilinks (a link target is not
// prose to correct). Each range carries the replacement to offer. `links` may
// carry the already-found wikilinks of `text`; they are sorted and disjoint,
// so one sweep along them replaces a search per word.
export function findDriftRanges(text, index, links) {
  if (!index || !index.size) return [];
  const spans = links || findWikilinks(text);
  const ranges = [];
  const pattern = new RegExp(WORD.source, 'gu');
  let next = 0;
  let match = pattern.exec(text);
  while (match) {
    const token = match[0];
    const start = match.index;
    const end = start + token.length;
    while (next < spans.length && spans[next].end <= start) next += 1;
    const inLink = next < spans.length && spans[next].start < end;
    const found = inLink ? null : driftFor(token, index);
    if (found) {
      ranges.push({
        start, end, kind: 'drift', word: token, from: found.pair.from, to: found.pair.to,
        replacement: matchCase(found.stem, found.pair.to) + found.suffix,
      });
    }
    match = pattern.exec(text);
  }
  return ranges;
}

// All marks for the text, in order and never overlapping.
export function buildMarks(text, statusMap, drift) {
  const links = findWikilinks(text);
  const problems = problemLinks(text, statusMap || new Map(), links).map((item) => ({
    start: item.start, end: item.end, kind: 'link-' + item.status,
  }));
  return problems.concat(findDriftRanges(text, drift, links)).sort((a, b) => a.start - b.start);
}

// Text cut into pieces at the mark edges: [{text, mark|null}].
export function segments(text, marks) {
  const pieces = [];
  let at = 0;
  marks.forEach((mark) => {
    if (mark.start < at) return;
    if (mark.start > at) pieces.push({ text: text.slice(at, mark.start), mark: null });
    pieces.push({ text: text.slice(mark.start, mark.end), mark });
    at = mark.end;
  });
  if (at < text.length) pieces.push({ text: text.slice(at), mark: null });
  return pieces;
}

// The drift range the caret sits in or against, for the inline hint.
export function driftAt(marks, caret) {
  return marks.find((mark) => mark.kind === 'drift' && caret >= mark.start && caret <= mark.end) || null;
}
