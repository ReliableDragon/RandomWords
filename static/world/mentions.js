// Upkeep's "Named but not linked": places where a note names another entry
// without linking to it, grouped by the entry that was named.

import { button, h, textNode } from './dom.js';
import { openEntry, stageReplacement } from './editor.js';
import { suggestionLink } from './nearby.js';
import { state } from './state.js';
import { displayPath, entryTitle } from './text.js';
import { dismissRow } from './triage.js';

const STAGE_MESSAGES = {
  stale: 'That note changed since Upkeep loaded. Refresh Upkeep and try again.',
  staged: 'Link staged. Review the highlighted link, then save.',
};

// -- Pure helpers ------------------------------------------------------------

// Splits a row's context around the matched text: [before, match, after].
export function splitContext(context, text) {
  const line = String(context || '');
  const word = String(text || '');
  let at = word ? line.indexOf(word) : -1;
  if (at < 0 && word) at = line.toLowerCase().indexOf(word.toLowerCase());
  if (at < 0) return [line, '', ''];
  return [line.slice(0, at), line.slice(at, at + word.length), line.slice(at + word.length)];
}

export function notActionableReason(row) {
  if (row.already_linked) return 'already linked in this note';
  if (!row.exact_case) return 'different capitalization';
  return 'not actionable';
}

export function pairKey(row) {
  return row.source_path + '|' + row.target_path;
}

// Dismissing "Not in this note" hides every mention of the target in that
// note, so the list shows one row per (note, target): the note's first
// mention, which is the one to link (as Obsidian does). Rows that cannot be
// linked are collapsed separately, so a note that also names the target in
// lowercase still lists that.
// Each returned row is a copy carrying `more` (other mentions of the same
// kind in the note) and, for the pair as a whole, `pairRows` (rows the list
// holds), `pairActionable` and `pairOccurrences` (all mentions, which is what
// a dismissal hides).
export function collapseMentions(rows) {
  const kept = new Map();
  const pairs = new Map();
  const collapsed = [];
  (rows || []).forEach((row) => {
    const pair = pairKey(row);
    const info = pairs.get(pair) || { rows: 0, actionable: 0, occurrences: 0 };
    pairs.set(pair, info);
    info.occurrences += 1;
    const key = pair + (row.actionable ? '|link' : '|other');
    if (kept.has(key)) {
      kept.get(key).more += 1;
      return;
    }
    info.rows += 1;
    if (row.actionable) info.actionable += 1;
    const copy = Object.assign({}, row, { more: 0, pair });
    kept.set(key, copy);
    collapsed.push(copy);
  });
  collapsed.forEach((row) => {
    const info = pairs.get(row.pair);
    row.pairRows = info.rows;
    row.pairActionable = info.actionable;
    row.pairOccurrences = info.occurrences;
  });
  return collapsed;
}

// The numbers the section shows: list rows (`rows`), those worth linking
// (`actionable`) and every mention behind them (`occurrences`).
export function mentionTotals(rows) {
  const collapsed = collapseMentions(rows);
  return {
    rows: collapsed.length,
    actionable: collapsed.filter((row) => row.actionable).length,
    occurrences: (rows || []).length,
  };
}

// Groups rows by the entry they name. Groups with something to act on come
// first, most-named first; the rest follow. `counts` is data.mention_counts.
export function groupMentions(rows, counts) {
  const noted = {};
  (counts || []).forEach((entry) => { noted[entry.target_path] = entry; });
  const groups = new Map();
  (rows || []).forEach((row) => {
    if (!groups.has(row.target_path)) {
      groups.set(row.target_path, {
        target_path: row.target_path,
        target_title: row.target_title,
        target_triage: row.target_triage,
        source: [],
      });
    }
    groups.get(row.target_path).source.push(row);
  });
  const list = Array.from(groups.values());
  list.forEach((group) => {
    group.occurrences = group.source.length;
    group.rows = collapseMentions(group.source);
    delete group.source;
  });
  list.forEach((group) => {
    group.actionable = group.rows.filter((row) => row.actionable);
    group.others = group.rows.filter((row) => !row.actionable);
    const sources = new Set(group.actionable.map((row) => row.source_path));
    const count = noted[group.target_path];
    group.notes = count ? count.notes : sources.size;
  });
  return list.sort((a, b) => (b.actionable.length > 0) - (a.actionable.length > 0)
    || b.notes - a.notes
    || b.occurrences - a.occurrences
    || String(a.target_title).localeCompare(String(b.target_title)));
}

export function groupHeading(group) {
  if (group.actionable.length) {
    const notes = group.notes;
    const noun = notes === 1 ? ' note' : ' notes';
    return group.target_title + ' — named in ' + notes + noun + ' without a link';
  }
  const n = group.occurrences;
  return group.target_title + ' — ' + n + (n === 1 ? ' mention' : ' mentions') + ', none to link';
}

// Target paths whose title is shared with another entry; a link to those
// must carry the full path or it would be ambiguous.
export function collidingPaths(collisions) {
  const paths = new Set();
  (collisions || []).forEach((row) => {
    (row.entries || []).forEach((entry) => paths.add(entry.path));
    (row.paths || []).forEach((path) => paths.add(path));
  });
  return paths;
}

// The wikilink to stage for a row, in the same form Nearby's "Link match" uses.
export function mentionLink(row, colliding) {
  const ambiguous = colliding && colliding.has(row.target_path);
  return suggestionLink({
    title: row.target_title,
    link_target: ambiguous ? displayPath(row.target_path) : row.target_title,
    expected: row.text,
  });
}

// -- Rows --------------------------------------------------------------------

function openSource(row) {
  return openEntry(row.source_path, { highlight: { start: row.start, end: row.end } });
}

// Opens the source note and stages the link there, unsaved. Refuses (with a
// notice) when the note's revision or the text at the span has changed.
export async function stageMention(row, colliding) {
  if (state.current !== row.source_path && !(await openSource(row))) return false;
  return stageReplacement({
    path: row.source_path, revision: row.source_revision, start: row.start, end: row.end, expected: row.text,
  }, mentionLink(row, colliding), STAGE_MESSAGES);
}

function contextLine(row) {
  const [before, match, after] = splitContext(row.context, row.text);
  const mark = match ? textNode('mark', match, 'drift-token') : null;
  return h('span', { class: 'drift-context' }, before, mark, after);
}

export function moreLabel(row) {
  return row.more > 0 ? '+' + row.more + ' more in this note' : '';
}

// `ctx` is {colliding, onChange, siblings, dismissed}: `siblings` maps a pair
// key to the row nodes on screen for it, so one dismissal can hide them all.
function mentionRow(row, ctx) {
  const line = h('div', { class: 'mention-row' + (row.actionable ? '' : ' is-muted') });
  const nodes = ctx.siblings.get(row.pair) || [];
  ctx.siblings.set(row.pair, nodes);
  nodes.push(line);
  const actions = h('div', { class: 'drift-actions' });
  if (row.actionable) {
    const stage = button('Stage link', 'btn btn-small btn-primary', () => stageMention(row, ctx.colliding));
    stage.title = 'Put the link in the note, unsaved, for review';
    actions.appendChild(stage);
  }
  actions.appendChild(button('Open', 'btn btn-small btn-quiet', () => openSource(row)));
  const hide = button('Not in this note', 'btn btn-small btn-quiet', () => dismissRow({
    node: line, triage: row.triage, label: 'Hidden for this note',
    onChange: (delta) => {
      nodes.forEach((node) => { if (node !== line) node.hidden = delta < 0; });
      if (delta < 0) ctx.dismissed.pairs.add(row.pair);
      else ctx.dismissed.pairs.delete(row.pair);
      ctx.onChange({
        dismissals: delta, rows: delta * row.pairRows, actionable: delta * row.pairActionable,
        occurrences: delta * row.pairOccurrences,
      });
    },
  }));
  hide.title = 'Stop listing this entry as unlinked in this note, however often it is named there';
  actions.appendChild(hide);
  const more = moreLabel(row);
  line.appendChild(h('div', { class: 'mention-body' },
    h('div', { class: 'mention-source' },
      textNode('strong', row.source_title || entryTitle({ path: row.source_path })),
      textNode('small', 'line ' + row.line, 'report-path'),
      more ? textNode('small', more, 'mention-more') : null,
      row.actionable ? null : textNode('small', notActionableReason(row), 'mention-tag')),
    contextLine(row)));
  line.appendChild(actions);
  return line;
}

function groupCard(group, showAll, ctx) {
  const rows = showAll ? group.rows : group.actionable;
  const card = h('article', { class: 'report-card mention-group' },
    h('div', { class: 'mention-group-head' },
      textNode('h4', groupHeading(group)),
      group.target_triage
        ? button('Never suggest', 'text-button', () => dismissRow({
          node: card, triage: group.target_triage, label: 'Won’t suggest ' + group.target_title,
          onChange: (delta) => {
            if (delta < 0) ctx.dismissed.targets.add(group.target_path);
            else ctx.dismissed.targets.delete(group.target_path);
            ctx.onChange({
              dismissals: delta, rows: delta * group.rows.length,
              actionable: delta * group.actionable.length, occurrences: delta * group.occurrences,
            });
          },
        }))
        : null),
    rows.map((row) => mentionRow(row, ctx)));
  return card;
}

// Rows left after this page's own dismissals, so a repaint does not bring
// them back before the report reloads. `dismissed` is {pairs, targets}.
export function visibleMentions(rows, dismissed) {
  if (!dismissed) return rows || [];
  return (rows || []).filter((row) => !dismissed.targets.has(row.target_path)
    && !dismissed.pairs.has(pairKey(row)));
}

export function newDismissed() {
  return { pairs: new Set(), targets: new Set() };
}

// The section body. `onChange({dismissals, rows, actionable, occurrences})`
// (negative on dismiss, positive on undo) lets the section keep its counts
// current; `rows` are list rows, `occurrences` every mention hidden.
// `showAll` and `dismissed` are kept by the caller.
export function mentionGroups(data, showAll, onChange, dismissed = newDismissed()) {
  const rows = visibleMentions((data.sections && data.sections.unlinked_mentions) || [], dismissed);
  const colliding = collidingPaths(data.sections && data.sections.name_collisions);
  const ctx = { colliding, onChange, siblings: new Map(), dismissed };
  return groupMentions(rows, data.mention_counts)
    .filter((group) => showAll || group.actionable.length)
    .map((group) => groupCard(group, showAll, ctx));
}
