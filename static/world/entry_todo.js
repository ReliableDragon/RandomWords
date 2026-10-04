// The to-do strip under an entry's title: what is still open on this entry.
//
//   #rework          tagged for another pass
//   N notes to self  ${...} asides; click jumps to the next one in the text
//   Stub             under 20 words
//   N unresolved / ambiguous links
//
// Each item shows only when it applies. The strip describes the saved entry:
// it comes from ENTRY_OPENED and is refreshed after a save (ENTRY_REFRESHED).

import { $, button, h } from './dom.js';
import { getText, showNotice } from './editor.js';
import { Events, on } from './events.js';
import { revealRange } from './reveal.js';
import { state } from './state.js';

// -- Pure helpers ----------------------------------------------------------

// Where the ${...} asides sit in `text`: [{start, end}] in order.
export function asideRanges(text) {
  const found = [];
  const pattern = /\$\{[^}]*\}/g;
  let match = pattern.exec(text || '');
  while (match) {
    found.push({ start: match.index, end: match.index + match[0].length });
    match = pattern.exec(text);
  }
  return found;
}

// The first range starting at or after `caret`, wrapping to the first one.
// A caret inside a range counts as past it, so repeated clicks keep moving.
export function nextRange(ranges, caret) {
  if (!ranges.length) return null;
  const after = ranges.find((range) => range.start > caret);
  return after || ranges[0];
}

// The first #tag (whole word, any case) in `text` as {start, end}, or null.
export function findTag(text, tag) {
  const escaped = String(tag).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp('(^|[^\\w#])(#' + escaped + ')(?![\\w-])', 'i').exec(text || '');
  if (!match) return null;
  const start = match.index + match[1].length;
  return { start, end: start + match[2].length };
}

const plural = (count, one, many) => count + ' ' + (count === 1 ? one : many);

// The to-do items for an entry as the server parsed it, and its link statuses:
// [{kind, label, action}], where action is 'tag', 'aside' or 'links' for an
// item that can take the writer somewhere, and null for one that cannot.
export function todoItems(entry, links) {
  if (!entry) return [];
  const items = [];
  const tags = Array.isArray(entry.tags) ? entry.tags : [];
  if (tags.some((tag) => String(tag).toLowerCase() === 'rework')) {
    items.push({ kind: 'rework', label: '#rework', action: 'tag' });
  }
  const notes = Array.isArray(entry.notes) ? entry.notes.length : 0;
  if (notes) items.push({ kind: 'notes', label: plural(notes, 'note to self', 'notes to self'), action: 'aside' });
  const words = typeof entry.words === 'number' ? entry.words : null;
  if (entry.stub === true) {
    items.push({ kind: 'stub', label: words == null ? 'Stub' : 'Stub, ' + plural(words, 'word', 'words'), action: null });
  }
  const statuses = Array.isArray(links) ? links : [];
  const unresolved = statuses.filter((link) => link.status === 'unresolved').length;
  const ambiguous = statuses.filter((link) => link.status === 'ambiguous').length;
  if (unresolved) items.push({ kind: 'unresolved', label: plural(unresolved, 'unresolved link', 'unresolved links'), action: 'links' });
  if (ambiguous) items.push({ kind: 'ambiguous', label: plural(ambiguous, 'ambiguous link', 'ambiguous links'), action: 'links' });
  return items;
}

// -- The strip -------------------------------------------------------------

function select(range) {
  const field = $('entryText');
  // A preview that replaces the text on a narrow screen has nothing to select.
  if ($('previewBtn') && state.preview && field.hidden) return;
  field.focus({ preventScroll: true });
  field.setSelectionRange(range.start, range.end);
  revealRange(field, range.start);
}

function jumpToAside() {
  const next = nextRange(asideRanges(getText()), $('entryText').selectionEnd || 0);
  if (next) select(next);
  else showNotice('No ${…} notes are left in the text. Save to update this list.');
}

function jumpToTag() {
  const found = findTag(getText(), 'rework');
  if (found) select(found);
  else showNotice('#rework is no longer in the text. Save to update this list.');
}

function showLinks() {
  const panel = $('linkStatus');
  if (panel && !panel.hidden && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

const ACTIONS = { tag: jumpToTag, aside: jumpToAside, links: showLinks };
const HINTS = {
  tag: 'Select #rework in the text',
  aside: 'Jump to the next ${…} note',
  links: 'Show the links that need attention',
};

function chip(item) {
  const className = 'todo-chip is-' + item.kind;
  if (!item.action) return h('span', { class: className }, item.label);
  const node = button(item.label, className + ' is-action', ACTIONS[item.action]);
  node.title = HINTS[item.action];
  return node;
}

export function renderTodo(entry, links) {
  const host = $('entryTodo');
  const items = todoItems(entry, links);
  host.replaceChildren();
  host.hidden = !items.length;
  if (!items.length) return;
  host.appendChild(h('span', { class: 'todo-lead' }, 'To do'));
  items.forEach((item) => host.appendChild(chip(item)));
}

function hideTodo() {
  const host = $('entryTodo');
  host.replaceChildren();
  host.hidden = true;
}

export function initEntryTodo() {
  on(Events.ENTRY_OPENING, hideTodo);
  on(Events.ENTRY_OPENED, (detail) => renderTodo(detail.entry, detail.links));
  on(Events.ENTRY_REFRESHED, (detail) => {
    if (detail.path === state.current) renderTodo(detail.entry, detail.links);
  });
}
