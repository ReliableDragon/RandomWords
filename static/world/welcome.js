// The welcome screen: pick up where you left off.
//
// Recent entries (the last few opened here), unsaved drafts kept on this
// device, and "Worth a look" from Upkeep. Recent entries and drafts come from
// browser storage and show at once; Worth a look is fetched after the rest is
// on screen, so the welcome never waits on the vault report.

import { world } from './api.js';
import { $, button, textNode } from './dom.js';
import { openEntry, resumeNewDraft } from './editor.js';
import { Events, on } from './events.js';
import { onWelcomeShown, setWorldView, showPane } from './nav.js';
import { state } from './state.js';
import { storage } from './storage.js';
import { entryTitle, folderParent } from './text.js';

const MAX_RECENT = 8;
const WORTH_LOOK = 3;
const HEALTH_MAX_AGE_MS = 60000;
const DAY_MS = 86400000;

// -- Pure helpers ----------------------------------------------------------

// `list` with `item` moved (or added) to the front, newest first, no repeats.
export function addRecent(list, item, max) {
  const rest = (list || []).filter((other) => other.path !== item.path);
  return [item].concat(rest).slice(0, max || MAX_RECENT);
}

export function dropRecent(list, path) {
  return (list || []).filter((item) => item.path !== path);
}

// "today", "yesterday", "3 days ago", or the date for older ones.
export function relativeTime(iso, now) {
  const then = Date.parse(iso || '');
  if (Number.isNaN(then)) return '';
  const at = new Date(then);
  const current = new Date(now == null ? Date.now() : now);
  const day = (date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.round((day(current) - day(at)) / DAY_MS);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return days + ' days ago';
  return at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// Unsaved drafts of both kinds as one list, newest first:
// {kind: 'new' | 'entry', key, title, detail, updated}. `key` is the draft id
// or the entry's path.
export function draftRows(newDrafts, entryDrafts) {
  const rows = [];
  (newDrafts || []).forEach((draft) => {
    rows.push({
      kind: 'new', key: draft.id, updated: draft.updated || '',
      title: (draft.title || '').trim() || 'Untitled entry',
      detail: 'New entry, not saved yet',
    });
  });
  (entryDrafts || []).forEach((draft) => {
    rows.push({
      kind: 'entry', key: draft.path, updated: draft.updated || '',
      title: entryTitle({ path: draft.path }),
      detail: 'Unsaved changes in ' + (folderParent(draft.path) || 'the vault root'),
    });
  });
  return rows.sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
}

// A long note to self is shown as its first part only.
export function clip(text, max) {
  const flat = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
  return flat.length <= max ? flat : flat.slice(0, max - 1).trimEnd() + '…';
}

const WORTH_KINDS = ['unresolved_links', 'notes_to_self', 'rework', 'stubs'];

// Up to three things worth opening, from an Upkeep report's sections: one
// each from different kinds, in a fixed order of usefulness. `seed` (say, the
// day number) moves which item of a kind is picked so it is not always the
// first. Each is {kind, path, title, text}.
export function worthALook(sections, seed, limit) {
  const found = [];
  const spin = Math.abs(Number(seed) || 0);
  WORTH_KINDS.forEach((kind) => {
    const rows = sections && Array.isArray(sections[kind]) ? sections[kind] : [];
    if (!rows.length || found.length >= (limit || WORTH_LOOK)) return;
    const row = rows[spin % rows.length];
    const title = row.title || entryTitle(row);
    const text = {
      unresolved_links: '"' + row.target + '" is linked from ' + title + ' but has no entry yet.',
      notes_to_self: title + ': a note to self, "' + clip(row.text, 90) + '".',
      rework: title + ' is marked #rework.',
      stubs: title + ' is a stub, ' + (row.words == null ? 'just a few' : row.words) + ' words so far.',
    }[kind];
    found.push({ kind, path: row.path, title, text });
  });
  return found;
}

// What the inline confirmation says before drafts are cleared. `open` is the
// title of the draft showing in the editor, or null.
export function clearSummary(counts, open) {
  const total = counts.drafts + counts.newDrafts;
  const what = total === 1 ? '1 unsaved draft' : total + ' unsaved drafts';
  let text = 'This removes ' + what + ' and any recovery copies from this browser. '
    + 'Nothing in your vault changes.';
  if (open) {
    text += ' It includes the draft open in the editor, "' + open + '". That text stays on screen but '
      + 'is no longer kept on this device until you change it again.';
  }
  return text;
}

// -- Recent entries --------------------------------------------------------

function recordOpened(detail) {
  if (!detail || !detail.path) return;
  const item = { path: detail.path, title: detail.title || entryTitle(detail), opened: new Date().toISOString() };
  storage.writeRecent(addRecent(storage.readRecent(), item, MAX_RECENT));
}

function recentRow(item) {
  const row = button('', 'welcome-row', () => openEntry(item.path));
  row.append(
    textNode('span', item.title || entryTitle(item), 'welcome-row-title'),
    textNode('span', (folderParent(item.path) || 'Vault root') + (item.opened ? ' · ' + relativeTime(item.opened) : ''), 'welcome-row-detail'));
  return row;
}

function renderRecent() {
  const items = storage.readRecent();
  $('welcomeRecent').hidden = !items.length;
  $('welcomeRecentList').replaceChildren(...items.map(recentRow));
}

// -- Drafts ----------------------------------------------------------------

function draftRow(row) {
  const open = () => {
    if (row.kind === 'new') {
      if (!resumeNewDraft(row.key)) renderDrafts();
    } else {
      openEntry(row.key);
    }
  };
  const node = button('', 'welcome-row', open);
  node.append(
    textNode('span', row.title, 'welcome-row-title'),
    textNode('span', row.detail + (row.updated ? ' · ' + relativeTime(row.updated) : ''), 'welcome-row-detail'));
  return node;
}

// The draft showing in the editor right now, as a title, or null.
function openDraftTitle() {
  if (state.newDraft) return (state.newDraft.title || '').trim() || 'Untitled entry';
  if (state.current && state.dirty) return entryTitle({ path: state.current });
  return null;
}

function hideConfirm() {
  $('welcomeClearConfirm').hidden = true;
  $('welcomeClear').hidden = false;
}

function renderDrafts() {
  const rows = draftRows(storage.listNewDrafts(), storage.listDrafts());
  $('welcomeDrafts').hidden = !rows.length;
  $('welcomeDraftList').replaceChildren(...rows.map(draftRow));
  if (!rows.length) hideConfirm();
}

function askToClear() {
  const counts = { drafts: storage.listDrafts().length, newDrafts: storage.listNewDrafts().length };
  $('welcomeClearText').textContent = clearSummary(counts, openDraftTitle());
  $('welcomeClear').hidden = true;
  $('welcomeClearConfirm').hidden = false;
  $('welcomeClearYes').focus();
}

function clearDrafts() {
  const cleared = storage.clearDrafts();
  hideConfirm();
  renderDrafts();
  const total = cleared.drafts + cleared.newDrafts;
  $('welcomeClearDone').textContent = 'Cleared ' + (total === 1 ? '1 draft' : total + ' drafts') + ' from this browser.';
}

// -- Worth a look ----------------------------------------------------------

let health = null; // {at, sections}
let healthSequence = 0;

function lookRow(item) {
  const node = button('', 'welcome-row', () => openEntry(item.path));
  node.append(textNode('span', item.text, 'welcome-row-title is-sentence'),
    textNode('span', 'Open ' + item.title, 'welcome-row-detail'));
  return node;
}

function renderLooks(sections) {
  const items = worthALook(sections, Math.floor(Date.now() / DAY_MS));
  $('welcomeLook').hidden = !items.length;
  $('welcomeLookList').replaceChildren(...items.map(lookRow));
  $('welcomeLookNote').hidden = true;
}

function showLooking() {
  $('welcomeLook').hidden = false;
  $('welcomeLookList').replaceChildren();
  $('welcomeLookNote').hidden = false;
}

async function loadLooks() {
  if (health && Date.now() - health.at < HEALTH_MAX_AGE_MS) {
    renderLooks(health.sections);
    return;
  }
  const mine = ++healthSequence;
  if (!health) showLooking();
  try {
    const data = await world.get('/health');
    if (mine !== healthSequence) return;
    health = { at: Date.now(), sections: data.sections || {} };
    renderLooks(health.sections);
  } catch (_) {
    // Worth a look is an extra; the welcome is complete without it.
    if (mine === healthSequence && !health) $('welcomeLook').hidden = true;
  }
}

// -- Wiring ----------------------------------------------------------------

// The entry or new draft still open behind the welcome, as a title, or null.
function openTitle() {
  if (state.newDraft) return (state.newDraft.title || '').trim() || 'Untitled entry';
  return state.current ? entryTitle({ path: state.current }) : null;
}

// Home keeps the editor as it is; Back returns to it unchanged.
function renderContinue() {
  const title = openTitle();
  $('welcomeContinue').hidden = !title;
  $('welcomeContinue').textContent = title ? 'Back to ' + title : '';
}

function goHome() {
  setWorldView('desk');
  showPane('welcome');
}

export function renderWelcome() {
  renderContinue();
  renderRecent();
  renderDrafts();
  $('welcomeClearDone').textContent = '';
  // After the rest is painted, so a slow vault report never delays it.
  setTimeout(() => { if (!$('welcome').hidden) loadLooks(); }, 0);
}

export function initWelcome() {
  on(Events.ENTRY_OPENED, recordOpened);
  onWelcomeShown(renderWelcome);
  $('homeBtn').addEventListener('click', goHome);
  $('welcomeContinue').addEventListener('click', () => showPane('entry'));
  $('welcomeClear').addEventListener('click', askToClear);
  $('welcomeClearYes').addEventListener('click', clearDrafts);
  $('welcomeClearKeep').addEventListener('click', hideConfirm);
  if (!$('welcome').hidden) renderWelcome();
}
