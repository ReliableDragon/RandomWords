// The Nearby panel: suggestions computed from the draft as you write.
//
// Suggestions carry the revision they were computed for and the exact text
// span they refer to. Both are rechecked before a one-click link edit so a
// late response can never touch newer text.

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { openCreate } from './create.js';
import { linksGeneration, noteGeneration, setFromTargets } from './draft_marks.js';
import { getText, refreshEntryData, renderPreview, replaceRange, insertAtCursor } from './editor.js';
import { renderMetadataSummary } from './entry_panels.js';
import { emit, Events, on } from './events.js';
import { addFromPlace } from './placement.js';
import { openReference } from './refcard.js';
import { nearbyPath, state } from './state.js';
import { entryTitle, pathFromResult } from './text.js';

const DEBOUNCE_MS = 500;

export const NEARBY_GROUPS = [
  ['named_not_linked', 'Named, not linked'],
  ['same_biome', 'Same biome'],
  ['same_tags', 'Same tags'],
  ['talks_about_same_things', 'Talks about the same things'],
  ['linked_from_what_you_link', 'Linked from what you link'],
];

// True when a "Link match" suggestion still applies to the text on screen.
// `original` is the draft the suggestion was computed from, `rev` the
// client revision sent with that request.
export function canApplySuggestion(suggestion, rev, original, now) {
  return String(suggestion.client_revision || rev) === rev
    && now === original
    && now.slice(suggestion.start, suggestion.end) === suggestion.expected;
}

// The wikilink that "Link match" inserts in place of the named text.
export function suggestionLink(suggestion) {
  const title = suggestion.title || entryTitle(suggestion);
  const target = String(suggestion.link_target || title).replace(/\.md$/i, '');
  const needsLabel = suggestion.expected !== title || target !== title;
  return '[[' + target + (needsLabel ? '|' + suggestion.expected : '') + ']]';
}

// The wikilink that "Insert link" adds at the caret.
export function nearbyLink(result) {
  const target = pathFromResult(result).replace(/\.md$/i, '');
  const title = result.title || entryTitle(result);
  return '[[' + target + (target === title ? '' : '|' + title) + ']]';
}

// The reason that names text which could be linked, shaped like an old
// "Named, not linked" card so Link match keeps its safety check. Null when
// the card has no such reason.
export function namedReason(card) {
  const reason = (card.reasons || []).find((item) => item.group === 'named_not_linked' && item.end != null);
  return reason ? Object.assign({}, reason, { title: card.title, path: card.path }) : null;
}

// What a merged card offers: pure, so it can be tested without a page.
export function cardOffers(card) {
  return {
    linkMatch: namedReason(card),
    insertLink: Boolean(pathFromResult(card)),
    useAsFrom: Boolean(card.is_place) && Boolean(pathFromResult(card)),
    namesake: Boolean(card.namesake),
  };
}

let timer = null;
let sequence = 0;

function setNote(text) {
  $('nearbyState').textContent = text;
}

function scheduleNearby() {
  clearTimeout(timer);
  if (!nearbyPath()) return;
  timer = setTimeout(loadNearby, DEBOUNCE_MS);
}

// A new draft reads as the file it would become, so renaming it or moving
// its folder while a request is out makes that answer stale.
export async function loadNearby() {
  const path = nearbyPath();
  if (!path) return;
  const mine = ++sequence;
  const rev = String(Date.now()) + '-' + mine;
  const text = getText();
  setNote('Reading draft…');
  try {
    const data = await world.post('/nearby', { text, path, client_revision: rev });
    // Another request, or another entry, has taken over since this began.
    if (mine !== sequence || nearbyPath() !== path) return;
    state.nearby = data;
    renderPreview(data.html, data.skipped);
    renderMetadataSummary(data.metadata);
    setFromTargets(data.metadata && data.metadata.from_targets);
    renderNearby(data, rev, text);
    setNote('Live suggestions');
    emit(Events.NEARBY_UPDATED, {
      path, groups: data.groups || {}, merged: data.merged || [],
    });
    noteVaultGeneration(data.generation);
  } catch (error) {
    if (mine === sequence) setNote(error.message);
  }
}

// A generation the page has not seen means the vault changed elsewhere, so
// link statuses and drift spellings may be out of date.
function noteVaultGeneration(generation) {
  if (generation == null) return;
  noteGeneration(generation);
  const known = linksGeneration();
  if (known !== null && known !== String(generation)) refreshEntryData();
}

function applySuggestion(suggestion, rev, original) {
  if (!canApplySuggestion(suggestion, rev, original, getText())) {
    scheduleNearby();
    setNote('Draft changed; refreshing suggestion');
    return;
  }
  replaceRange(suggestion.start, suggestion.end, suggestionLink(suggestion));
}

// "Use as From" on a new draft puts the place on that draft's From: line; on
// a saved entry it starts a new draft that comes from the place.
function useAsFrom(path, title) {
  if (state.newDraft) addFromPlace({ path, title });
  else openCreate({ fromTargets: [{ path, title }] });
}

function cardActions(result) {
  const path = pathFromResult(result);
  if (!path) return h('div', { class: 'nearby-actions' });
  return h('div', { class: 'nearby-actions' },
    button('Insert link', 'btn btn-small btn-quiet', () => insertAtCursor(nearbyLink(result))),
    button('Use as From', 'text-button', () => useAsFrom(path, result.title || entryTitle(result))));
}

function mergedCard(card, rev, text) {
  const offers = cardOffers(card);
  const path = pathFromResult(card);
  const name = card.title || entryTitle(card);
  const title = button(name, 'nearby-title', () => openReference(path));
  const top = h('div', { class: 'nearby-card-top' }, title);
  const actions = h('div', { class: 'nearby-actions' });
  if (offers.linkMatch) {
    const match = button('Link match', 'btn btn-small btn-quiet link-suggestion',
      () => applySuggestion(offers.linkMatch, rev, text));
    match.setAttribute('aria-label', 'Link the matching text to ' + name);
    top.appendChild(match);
  }
  if (offers.insertLink) {
    const insert = button('Insert link', 'btn btn-small btn-quiet', () => insertAtCursor(nearbyLink(card)));
    insert.setAttribute('aria-label', 'Insert link to ' + name);
    actions.appendChild(insert);
  }
  if (offers.useAsFrom) {
    const from = button('Use as From', 'text-button', () => useAsFrom(path, name));
    from.setAttribute('aria-label', state.newDraft
      ? 'Use ' + name + ' as From for this draft' : 'Use ' + name + ' as From for a new entry');
    actions.appendChild(from);
  }
  const reasons = h('ul', { class: 'nearby-reasons' },
    (card.reasons || []).map((reason) => textNode('li', reason.text, 'nearby-chip is-' + reason.group)));
  return h('article', { class: 'nearby-card' }, top,
    textNode('span', card.folder || path, 'nearby-folder'),
    offers.namesake ? textNode('span', 'Same name, different entry', 'nearby-badge') : null,
    reasons, actions);
}

function nearbyCard(groupKey, result, rev, text) {
  const top = h('div', { class: 'nearby-card-top' },
    button(result.title || entryTitle(result), 'nearby-title', () => openReference(pathFromResult(result))));
  if (groupKey === 'named_not_linked') {
    top.appendChild(button('Link match', 'btn btn-small btn-quiet link-suggestion', () => applySuggestion(result, rev, text)));
  }
  const card = h('article', { class: 'nearby-card' }, top, cardActions(result),
    textNode('span', result.folder || result.path || '', 'nearby-folder'));
  if (result.reason) card.appendChild(textNode('span', result.reason, 'nearby-reason'));
  return card;
}

function nearbyGroup(key, label, list, rev, text) {
  return h('section', { class: 'nearby-group' },
    h('h3', null, label + ' ', h('span', null, list.length)),
    h('div', { class: 'nearby-cards' }, list.map((result) => nearbyCard(key, result, rev, text))));
}

function renderNearby(data, rev, text) {
  const host = $('nearbyGroups');
  host.replaceChildren();
  if (Array.isArray(data.merged)) {
    if (data.merged.length) {
      host.appendChild(h('div', { class: 'nearby-cards nearby-merged' },
        data.merged.map((card) => mergedCard(card, rev, text))));
    } else {
      host.appendChild(emptyNote());
    }
    return;
  }
  renderGroups(data.groups || {}, rev, text, host);
}

function emptyNote() {
  return textNode('p', 'No nearby entries yet. Add references, places, or tags as you write.', 'muted nearby-empty');
}

// Older servers answer with the five groups only.
function renderGroups(groups, rev, text, host) {
  NEARBY_GROUPS.forEach(([key, label]) => {
    const list = groups[key] || [];
    if (list.length) host.appendChild(nearbyGroup(key, label, list, rev, text));
  });
  if (!host.childNodes.length) host.appendChild(emptyNote());
}

// A different entry is opening: nothing computed for the old one applies.
function forgetOldEntry() {
  clearTimeout(timer);
  sequence++;
  state.nearby = null;
  $('nearbyGroups').replaceChildren();
}

export function initNearby() {
  on(Events.ENTRY_OPENING, forgetOldEntry);
  on(Events.DRAFT_CHANGED, scheduleNearby);
}
