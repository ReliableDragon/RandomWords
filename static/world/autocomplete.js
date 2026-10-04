// Wikilink ([[) and tag (#) completion in the editor textarea.

import { world } from './api.js';
import { $, h } from './dom.js';
import { Events, on } from './events.js';
import { replaceRange } from './editor.js';
import { state } from './state.js';
import { entryTitle } from './text.js';

const MAX_LINK_ITEMS = 8;
const MAX_TAG_ITEMS = 10;
const LOOKUP_DELAY_MS = 120;

// What the writer is typing, from the text before the caret. Returns
// {token: 'link' | 'tag', marker, start, query} or null. `marker` is where
// the [[ or # begins; `start` where the query text begins.
export function parseTrigger(before) {
  const match = before.match(/(?:\[\[|#)([^\]\n#]*)$/);
  if (!match) return null;
  const query = match[1];
  const isTag = match[0].charAt(0) === '#';
  return {
    token: isTag ? 'tag' : 'link',
    marker: before.lastIndexOf(isTag ? '#' : '[['),
    start: before.length - query.length,
    query,
  };
}

// Tag routes answer with a list of names or {tag|name} objects.
export function tagCompletions(response, query) {
  const tags = Array.isArray(response) ? response : (response.tags || []);
  const wanted = ('#' + query).toLocaleLowerCase();
  return tags
    .map((tag) => (typeof tag === 'string' ? tag : (tag.tag || tag.name || '')))
    .filter(Boolean)
    .map((tag) => (tag.charAt(0) === '#' ? tag : '#' + tag))
    .filter((tag) => tag.toLocaleLowerCase().indexOf(wanted) === 0)
    .slice(0, MAX_TAG_ITEMS)
    .map((tag) => ({ title: tag, path: '' }));
}

// Entries the Nearby panel already suggests come first.
export function prioritizeNearby(results, nearbyPaths) {
  const rank = (result) => (nearbyPaths.indexOf(result.path) < 0 ? 1 : 0);
  return results.slice().sort((a, b) => rank(a) - rank(b));
}

// The list for a bare [[: what Nearby ranks first (merged cards, best first),
// as completion items. Empty when Nearby has nothing yet.
export function nearbyItems(nearby, limit) {
  const merged = (nearby && Array.isArray(nearby.merged)) ? nearby.merged : [];
  return merged
    .filter((card) => card && card.path)
    .slice(0, limit || MAX_LINK_ITEMS)
    .map((card) => ({ path: card.path, title: card.title, folder: card.folder }));
}

// Where the highlight goes for an arrow key. -1 means nothing is highlighted;
// Down from nothing lands on the first option and Up on the last.
export function moveHighlight(current, count, key) {
  if (!count) return -1;
  if (key === 'ArrowDown') return current < 0 ? 0 : (current + 1) % count;
  return current <= 0 ? count - 1 : current - 1;
}

// Enter and Tab belong to the list only while one of its options is highlighted.
export function capturesKey(key, listOpen, highlighted) {
  return listOpen && highlighted >= 0 && (key === 'Enter' || key === 'Tab');
}

function lower(value) {
  return String(value).toLocaleLowerCase();
}

// The text to insert for the chosen item. Titles shared by several entries
// are written as paths; an alias the writer was typing is kept as the label.
export function completionText(trigger, item, items) {
  if (trigger.token === 'tag') return item.title;
  const title = item.title || entryTitle(item);
  const query = lower(trigger.query || '');
  const alias = (item.aliases || []).find((name) => typeof name === 'string'
    && lower(name).indexOf(query) === 0 && lower(name) !== lower(title));
  const ambiguous = items.filter((other) => lower(other.title || entryTitle(other)) === lower(title)).length > 1;
  const target = ambiguous
    ? (item.path || ((item.folder || '') + '/' + title)).replace(/\.md$/i, '')
    : title;
  const label = alias || title;
  return '[[' + target + (label !== title ? '|' + label : '') + ']]';
}

// The [[link]] for an entry chosen outside a typed [[ (a From place, say):
// its title when no other entry in `others` shares it, else its path.
export function linkFor(entry, others) {
  const item = { path: entry.path, title: entry.title || entryTitle(entry), folder: entry.folder };
  const all = (others || []).some((other) => other.path === item.path) ? others : (others || []).concat([item]);
  return completionText({ token: 'link', query: '' }, item, all);
}

let trigger = null;
let items = [];
let index = -1;
let sequence = 0;
let lookupTimer = null;

// Keeps the textarea's popup attributes in step with the list.
function syncAria() {
  const field = $('entryText');
  const open = !$('autocomplete').hidden;
  field.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open && index >= 0) field.setAttribute('aria-activedescendant', 'autocompleteOption' + index);
  else field.removeAttribute('aria-activedescendant');
}

export function hideAutocomplete() {
  sequence++; // a lookup still in flight must not reopen the list
  clearTimeout(lookupTimer);
  $('autocomplete').hidden = true;
  trigger = null;
  index = -1;
  syncAria();
}

// A typed query highlights its best match; a bare trigger highlights nothing,
// so Enter keeps writing a new line until the writer picks an option.
function showCompletions(list, query) {
  items = list;
  index = list.length && query ? 0 : -1;
  const host = $('autocomplete');
  host.replaceChildren();
  list.forEach((item, position) => {
    const option = h('button', {
      type: 'button', role: 'option', id: 'autocompleteOption' + position, tabindex: '-1',
      'aria-selected': position === index ? 'true' : 'false',
    },
      h('strong', null, item.title || entryTitle(item)),
      h('small', null, item.folder || item.path || ''));
    // mousedown, not click: the textarea must keep its caret.
    option.addEventListener('mousedown', (event) => {
      event.preventDefault();
      choose(position);
    });
    host.appendChild(option);
  });
  host.hidden = !list.length;
  syncAria();
}

function nearbyPaths() {
  const nearby = state.nearby || {};
  if (Array.isArray(nearby.merged)) return nearby.merged.map((card) => card.path);
  const groups = nearby.groups || {};
  return Object.keys(groups).reduce((paths, name) => paths.concat((groups[name] || []).map((x) => x.path)), []);
}

async function complete(found) {
  const mine = ++sequence;
  try {
    if (found.token === 'tag') {
      const response = await world.get('/tags');
      if (mine === sequence) showCompletions(tagCompletions(response, found.query), found.query);
      return;
    }
    const data = await world.get('/search', { q: found.query });
    if (mine === sequence) {
      const results = prioritizeNearby(data.results || [], nearbyPaths()).slice(0, MAX_LINK_ITEMS);
      showCompletions(results, found.query);
    }
  } catch (_) {
    if (mine === sequence) hideAutocomplete();
  }
}

function detect() {
  const field = $('entryText');
  const before = field.value.slice(0, field.selectionStart);
  const found = parseTrigger(before);
  if (!found) {
    hideAutocomplete();
    return;
  }
  trigger = found;
  const mine = ++sequence;
  clearTimeout(lookupTimer);
  const ranked = found.token === 'link' && !found.query ? nearbyItems(state.nearby) : [];
  if (ranked.length) {
    showCompletions(ranked, '');
    return;
  }
  // Each keystroke restarts the wait; `complete` drops answers that arrive late.
  lookupTimer = setTimeout(() => {
    if (mine === sequence) complete(found);
  }, LOOKUP_DELAY_MS);
}

function choose(position) {
  const item = items[position];
  if (!trigger || !item) return;
  const text = completionText(trigger, item, items);
  const end = $('entryText').selectionStart;
  const marker = trigger.marker;
  hideAutocomplete();
  replaceRange(marker, end, text);
}

function highlight(position) {
  index = position;
  Array.from($('autocomplete').children).forEach((option, i) => {
    option.setAttribute('aria-selected', i === index ? 'true' : 'false');
  });
  const active = $('autocomplete').children[index];
  if (active && active.scrollIntoView) active.scrollIntoView({ block: 'nearest' });
  syncAria();
}

function onKeydown(event) {
  const open = !$('autocomplete').hidden;
  if (!open) return;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    highlight(moveHighlight(index, items.length, event.key));
  } else if (capturesKey(event.key, open, index)) {
    event.preventDefault();
    choose(index);
  } else if (event.key === 'Escape') {
    event.preventDefault();
    hideAutocomplete();
  }
}

export function initAutocomplete() {
  const field = $('entryText');
  field.addEventListener('input', detect);
  field.addEventListener('keydown', onKeydown);
  field.addEventListener('blur', hideAutocomplete);
  on(Events.ENTRY_OPENING, hideAutocomplete);
}
