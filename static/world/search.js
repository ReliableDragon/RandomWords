// The sidebar "Find an entry" box.
//
// Each result says how it matched: the title, an alias ("alias of …") or the
// text (a snippet with the match marked). Results are buttons, so arrow keys
// move between them and Enter opens the focused one.

import { world } from './api.js';
import { $, h, textNode } from './dom.js';
import { openEntry } from './editor.js';
import { entryTitle } from './text.js';

const DEBOUNCE_MS = 180;
const MAX_RESULTS = 30;

let timer = null;
let sequence = 0;
let shownSequence = 0; // the search whose results are on screen

// -- Pure helpers (also used by the tests) -----------------------------------

// {before, match, after} for a full-text hit, or null when there is no snippet.
export function snippetParts(result, query) {
  const text = result && result.snippet;
  if (typeof text !== 'string' || !text) return null;
  const span = Array.isArray(result.snippet_match) ? result.snippet_match : null;
  const needle = String(query || '').trim().toLowerCase();
  let start = -1;
  let end = -1;
  if (span && span[0] >= 0 && span[1] > span[0] && span[1] <= text.length
    && (!needle || text.slice(span[0], span[1]).toLowerCase() === needle)) {
    [start, end] = span;
  } else if (needle) {
    start = text.toLowerCase().indexOf(needle);
    end = start + needle.length;
  }
  if (start < 0) return { before: text, match: '', after: '' };
  return { before: text.slice(0, start), match: text.slice(start, end), after: text.slice(end) };
}

// Titles that occur more than once, so the folder can tell them apart.
export function duplicateTitles(results) {
  const seen = new Map();
  results.forEach((row) => {
    const key = (row.title || entryTitle(row)).toLowerCase();
    seen.set(key, (seen.get(key) || 0) + 1);
  });
  return new Set(Array.from(seen.keys()).filter((key) => seen.get(key) > 1));
}

export function countMessage(count, shown) {
  if (!count) return 'No matches.';
  const noun = count === 1 ? 'result' : 'results';
  return shown < count ? shown + ' of ' + count + ' results shown.' : count + ' ' + noun + '.';
}

// Which alias matched, or null. The server says so; older replies are checked here.
export function matchedAlias(result, query) {
  if (result.match === 'alias' && result.matched_alias) return result.matched_alias;
  if (result.match) return null;
  const needle = String(query || '').trim().toLowerCase();
  const title = String(result.title || '').toLowerCase();
  if (!needle || title.indexOf(needle) >= 0) return null;
  return (result.aliases || []).find((alias) => String(alias).toLowerCase().indexOf(needle) >= 0) || null;
}

// -- Rendering ---------------------------------------------------------------

function wordsLabel(result) {
  return result.words == null ? '' : result.words + (result.words === 1 ? ' word' : ' words');
}

function detailLine(result, query) {
  const alias = matchedAlias(result, query);
  if (alias) return h('span', { class: 'search-result-why' }, 'alias of ', h('em', null, alias));
  const parts = snippetParts(result, query);
  if (!parts) return null;
  return h('span', { class: 'search-result-snippet' }, parts.before,
    parts.match ? h('mark', null, parts.match) : null, parts.after);
}

function resultRow(result, query, duplicate) {
  const title = result.title || entryTitle(result);
  const row = h('button', { type: 'button', class: 'search-result', 'data-path': result.path },
    h('span', { class: 'search-result-top' },
      textNode('span', title, 'search-result-title'),
      result.kind ? textNode('span', result.kind, 'search-chip') : null,
      result.stub ? textNode('span', 'stub', 'search-chip is-stub') : null,
      textNode('span', wordsLabel(result), 'search-result-words')),
    textNode('span', result.folder || '', 'search-result-folder' + (duplicate ? ' is-duplicate' : '')),
    detailLine(result, query));
  row.addEventListener('click', () => choose(result));
  row.addEventListener('keydown', (event) => moveFocus(event, row));
  return row;
}

function choose(result) {
  closeResults();
  $('worldSearch').value = '';
  openEntry(result.path);
}

function resultButtons() {
  return Array.from($('searchResults').querySelectorAll('.search-result'));
}

function closeResults() {
  $('searchResults').hidden = true;
  $('worldSearch').setAttribute('aria-expanded', 'false');
  $('searchStatus').textContent = '';
}

function moveFocus(event, row) {
  const buttons = resultButtons();
  const at = buttons.indexOf(row);
  let next = null;
  if (event.key === 'ArrowDown') next = buttons[Math.min(buttons.length - 1, at + 1)];
  else if (event.key === 'ArrowUp') next = at > 0 ? buttons[at - 1] : $('worldSearch');
  else if (event.key === 'Home') next = buttons[0];
  else if (event.key === 'End') next = buttons[buttons.length - 1];
  else if (event.key === 'Escape') next = $('worldSearch');
  if (!next) return;
  event.preventDefault();
  next.focus();
  if (event.key === 'Escape') closeResults();
}

function renderResults(results, query) {
  const host = $('searchResults');
  const shown = results.slice(0, MAX_RESULTS);
  host.replaceChildren();
  host.hidden = false;
  $('worldSearch').setAttribute('aria-expanded', 'true');
  $('searchStatus').textContent = countMessage(results.length, shown.length);
  if (!shown.length) {
    host.appendChild(h('p', { class: 'muted' }, 'No matches.'));
    return;
  }
  const repeated = duplicateTitles(shown);
  shown.forEach((result) => {
    host.appendChild(resultRow(result, query, repeated.has((result.title || entryTitle(result)).toLowerCase())));
  });
}

async function runSearch(query) {
  const mine = ++sequence;
  try {
    const data = await world.get('/search', { q: query });
    if (mine !== sequence) return;
    shownSequence = mine;
    renderResults(data.results || [], query);
  } catch (error) {
    if (mine !== sequence) return;
    const host = $('searchResults');
    host.replaceChildren(h('p', { class: 'tree-error' }, error.message));
    host.hidden = false;
  }
}

function inputKey(event) {
  if (event.key === 'Escape') {
    if (!$('searchResults').hidden) {
      event.preventDefault();
      closeResults();
    }
    return;
  }
  const first = resultButtons()[0];
  if (!first || $('searchResults').hidden) return;
  if (event.key === 'ArrowDown' || (event.key === 'Enter' && !timer && shownSequence === sequence)) {
    event.preventDefault();
    if (event.key === 'Enter') first.click();
    else first.focus();
  }
}

export function initSearch() {
  const input = $('worldSearch');
  input.addEventListener('input', (event) => {
    clearTimeout(timer);
    const query = event.target.value.trim();
    if (!query) {
      timer = null;
      sequence++;
      closeResults();
      return;
    }
    timer = setTimeout(() => {
      timer = null;
      runSearch(query);
    }, DEBOUNCE_MS);
  });
  input.addEventListener('keydown', inputKey);
}
