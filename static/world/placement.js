// The placement bar and panel on a new draft: where the entry will live.
//
// Writing comes first; placing happens when the writer is ready. The bar
// under the title says "Lives in: folder · From place · Template · Change".
// Change opens a panel to pick a kind, a place, a folder and a template. A
// place goes onto the draft's From: line as text, and a template's headings
// go into the text only while the writer has not written anything below the
// header lines. Everything here edits the draft in state.newDraft.

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { linkFor } from './autocomplete.js';
import {
  addFromLink, appendTemplate, fromLinks, hasFromLink, headerEnd, linkTargetOf, placeTemplate, placementParts, removeFromLink,
  sameTarget, templateLabel,
} from './draft_text.js';
import { applyTextChange, getText, setDirty } from './editor.js';
import { emit, Events, on } from './events.js';
import { state } from './state.js';
import { storage } from './storage.js';
import { entryTitle, folderParent } from './text.js';
import { walkVault } from './tree.js';

const SEARCH_DEBOUNCE_MS = 180;
const MAX_FOLDER_MATCHES = 10;
const MAX_PLACE_MATCHES = 8;
const CACHE_MS = 60000;

let panelOpen = false;
let kinds = [];
let kindsAt = 0;
let templates = []; // [{path, label}]
let templatesAt = 0;
let vaultFolders = [];
let vaultFoldersLoaded = false;
let vaultFoldersLoading = false;
let folderBrowsing = ''; // the folder level the chooser lists
let folderSequence = 0; // guards against out-of-order folder listings
let proposalSequence = 0; // guards against out-of-order /placement answers
let suggestedKind = '';
let pendingTemplate = null; // {path, text}: offered at the end of the text
let placeTimer = null;
let placeSequence = 0;

// -- Sorting search hits ---------------------------------------------------

// Places (Locations/) first, then the rest in the order the server gave.
export function placesFirst(results) {
  const isPlace = (row) => String(row.path || '').indexOf('Locations/') === 0;
  return results.filter(isPlace).concat(results.filter((row) => !isPlace(row)));
}

// -- The bar ---------------------------------------------------------------

function showIssue(message) {
  const note = $('placementIssue');
  note.textContent = message || '';
  note.hidden = !message;
}

// Draws the one-line summary from the draft and its From: line.
export function renderBar() {
  const draft = state.newDraft;
  if (!draft) return;
  const parts = placementParts(draft, getText());
  $('placementSummary').replaceChildren(
    textNode('span', parts.short, 'placement-short'),
    h('span', { class: 'placement-lives' }, 'Lives in: ',
      textNode('strong', parts.folder || 'not chosen yet', parts.folder ? '' : 'is-missing')),
    parts.names.length
      ? h('span', { class: 'placement-from' }, 'From ', textNode('strong', parts.names.join(', ')))
      : textNode('span', 'No place yet', 'placement-from is-empty'),
    textNode('span', parts.template || 'No template', 'placement-template'));
  $('placementChange').setAttribute('aria-expanded', panelOpen ? 'true' : 'false');
  if (panelOpen) renderChosenPlaces();
}

// -- Kinds -----------------------------------------------------------------

async function loadKinds() {
  if (kinds.length && Date.now() - kindsAt < CACHE_MS) return;
  try {
    // A bare /placement answers with just the kinds (Coverage's columns).
    const data = await world.get('/placement');
    kinds = data.kinds || kinds;
    kindsAt = Date.now();
  } catch (_) {
    // Without kinds the chips stay empty; place and folder still work.
  }
  renderKinds();
}

function renderKinds() {
  const draft = state.newDraft;
  const host = $('placementKinds');
  host.replaceChildren();
  if (!draft) return;
  if (!kinds.length) {
    host.appendChild(textNode('span', 'Loading kinds…', 'muted'));
    return;
  }
  kinds.forEach((kind) => {
    const on = draft.kind === kind;
    const chip = button(kind, 'placement-chip' + (on ? ' is-on' : '') + (suggestedKind === kind && !draft.kind ? ' is-suggested' : ''),
      () => chooseKind(on ? '' : kind));
    chip.setAttribute('aria-pressed', on ? 'true' : 'false');
    host.appendChild(chip);
  });
  const note = $('placementSuggest');
  note.replaceChildren();
  note.hidden = !(suggestedKind && !draft.kind);
  if (!note.hidden) {
    note.append('Most entries from this place are ' + suggestedKind + '. ',
      button('Use ' + suggestedKind, 'text-button placement-link', () => chooseKind(suggestedKind)));
  }
}

async function chooseKind(kind) {
  const draft = state.newDraft;
  if (!draft) return;
  draft.kind = kind;
  suggestedKind = '';
  setDirty();
  renderKinds();
  if (kind) await proposePlacement({ explicitKind: true });
}

// -- Proposals from /placement ---------------------------------------------

function lastFromPath() {
  const draft = state.newDraft;
  return draft && draft.fromTargets.length ? draft.fromTargets[draft.fromTargets.length - 1].path : '';
}

async function folderExists(path) {
  try {
    await world.get('/tree', { path });
    return true;
  } catch (_) {
    return false;
  }
}

// Asks the server where this place and kind would live and offers it: the
// folder (unless the writer chose their own), a template, a suggested kind.
async function proposePlacement(options) {
  const draft = state.newDraft;
  const query = {};
  const from = lastFromPath();
  if (from) query.from = from;
  if (draft && draft.kind) query.kind = draft.kind;
  if (!draft || (!query.from && !query.kind)) return;
  const mine = ++proposalSequence;
  let data;
  try {
    data = await world.get('/placement', query);
  } catch (error) {
    if (mine === proposalSequence && state.newDraft === draft) showPanelNote(error.message);
    return;
  }
  if (mine !== proposalSequence || state.newDraft !== draft) return;
  if (Array.isArray(data.kinds) && data.kinds.length) {
    kinds = data.kinds;
    kindsAt = Date.now();
  }
  suggestedKind = !draft.kind && data.suggested_kind ? data.suggested_kind : '';
  if (data.folder) await proposeFolder(data.folder, Boolean(options && options.explicitKind));
  if (mine !== proposalSequence || state.newDraft !== draft) return;
  if (data.template) await chooseTemplate(data.template);
  setDirty();
  renderKinds();
  renderBar();
}

// A suggested folder is only used if it exists, and never replaces a folder
// the writer chose themselves unless they picked a kind just now.
async function proposeFolder(folder, explicit) {
  const draft = state.newDraft;
  if (!explicit && draft.folder != null && draft.folderSource !== 'proposed') return;
  if (await folderExists(folder)) {
    if (state.newDraft !== draft) return;
    draft.folder = folder;
    draft.folderSource = 'proposed';
    showIssue('');
    emit(Events.DRAFT_CHANGED); // the path Nearby reads has moved
    if (panelOpen) renderFolderValue();
  } else {
    showPanelNote('The suggested folder "' + folder + '" is not in this vault yet. Choose a folder below.');
    openFolderChooser();
  }
}

function showPanelNote(message) {
  const note = $('placementNote');
  note.textContent = message || '';
  note.hidden = !message;
}

// -- Places ----------------------------------------------------------------

function renderChosenPlaces() {
  const host = $('placeChosen');
  host.replaceChildren();
  fromLinks(getText()).forEach((link) => {
    const remove = button('×', 'placement-chip-remove', () => removePlace(link.target));
    remove.setAttribute('aria-label', 'Remove ' + link.display + ' from From');
    host.appendChild(h('span', { class: 'placement-chip is-place' }, link.display, remove));
  });
}

function removePlace(target) {
  const draft = state.newDraft;
  if (!draft) return;
  applyTextChange(removeFromLink(getText(), target));
  draft.fromTargets = draft.fromTargets.filter((item) => !sameTarget(target, item.path));
  setDirty();
  renderBar();
}

// Adds a place to the draft's From: line (a title when it is unique, a path
// when not) and asks where an entry from there would live. `siblings` are
// other search hits, used to tell whether the title is shared.
export async function addFromPlace(place, siblings) {
  const draft = state.newDraft;
  if (!draft || !/\.md$/i.test(place.path || '')) return false;
  const title = place.title || entryTitle(place);
  const link = linkFor({ path: place.path, title, folder: place.folder }, siblings || await sameTitleHits(title));
  if (state.newDraft !== draft) return false;
  if (!hasFromLink(getText(), linkTargetOf(link)) && !hasFromLink(getText(), place.path)) {
    const next = addFromLink(getText(), link);
    if (next === null) {
      showPanelNote('The From line is in the frontmatter. Edit that raw field directly.');
      return false;
    }
    applyTextChange(next);
  }
  if (!draft.fromTargets.some((item) => item.path === place.path)) draft.fromTargets.push({ path: place.path, title });
  setDirty();
  renderBar();
  await proposePlacement({});
  return true;
}

async function sameTitleHits(title) {
  try {
    return (await world.get('/search', { q: title })).results || [];
  } catch (_) {
    return [];
  }
}

function renderPlaceResults(rows) {
  const host = $('placeResults');
  host.replaceChildren();
  const shown = placesFirst(rows).slice(0, MAX_PLACE_MATCHES);
  shown.forEach((row) => {
    const title = row.title || entryTitle(row);
    host.appendChild(button([textNode('strong', title), textNode('small', row.path)], 'create-search-result',
      () => {
        $('placeSearch').value = '';
        host.replaceChildren();
        addFromPlace(row, rows);
      }));
  });
  if (!shown.length) host.appendChild(textNode('p', 'No matching entries.', 'muted'));
}

function findPlaces(event) {
  const query = event.target.value.trim();
  clearTimeout(placeTimer);
  const mine = ++placeSequence;
  if (!query) {
    $('placeResults').replaceChildren();
    return;
  }
  placeTimer = setTimeout(async () => {
    try {
      const data = await world.get('/search', { q: query });
      if (mine === placeSequence) renderPlaceResults(data.results || []);
    } catch (_) {
      // Searching is optional; leave the previous results.
    }
  }, SEARCH_DEBOUNCE_MS);
}

// -- Templates -------------------------------------------------------------

async function loadTemplates() {
  if (templates.length && Date.now() - templatesAt < CACHE_MS) {
    fillTemplates();
    return;
  }
  try {
    const data = await world.get('/tree', { path: 'Templates' });
    templates = (data.entries || [])
      .filter((item) => !item.is_dir && /\.md$/i.test(item.path || item.name || ''))
      .map((item) => ({ path: item.path || 'Templates/' + item.name, label: templateLabel(item.path || item.name) }))
      .sort((a, b) => a.label.localeCompare(b.label));
    templatesAt = Date.now();
  } catch (_) {
    templates = [];
  }
  fillTemplates();
}

function fillTemplates() {
  const draft = state.newDraft;
  const select = $('newTemplate');
  select.replaceChildren(new Option('No template', ''));
  templates.forEach((item) => select.appendChild(new Option(item.label, item.path)));
  if (draft && draft.template && !templates.some((item) => item.path === draft.template)) {
    select.appendChild(new Option(templateLabel(draft.template), draft.template));
  }
  select.value = draft ? draft.template || '' : '';
}

function showEndOffer() {
  const offer = $('templateInsertEnd');
  offer.hidden = !pendingTemplate;
}

// Records the template on the draft and puts its headings in: under the
// header lines while nothing is written there, otherwise offered at the end.
export async function chooseTemplate(path) {
  const draft = state.newDraft;
  if (!draft) return;
  draft.template = path || '';
  pendingTemplate = null;
  if (panelOpen) $('newTemplate').value = draft.template;
  if (path) {
    let text = '';
    try {
      text = (await world.get('/entry', { path })).text || '';
    } catch (error) {
      showPanelNote('Could not read that template. ' + error.message);
    }
    if (state.newDraft !== draft || draft.template !== path) return;
    const before = getText();
    const caret = $('entryText').selectionStart;
    const result = placeTemplate(before, text, draft.insertedTemplate);
    if (result.placed) {
      applyTextChange(result.text);
      draft.insertedTemplate = text;
      // A caret resting below the header lines moves under the first heading,
      // so the writer starts in the first section.
      if (caret >= headerEnd(before)) moveCaretUnderFirstHeading(result.text, result.start);
    } else if (text.trim()) {
      pendingTemplate = { path, text };
    }
  }
  showEndOffer();
  setDirty();
  renderBar();
}

function moveCaretUnderFirstHeading(text, start) {
  const lineEnd = text.indexOf('\n', start);
  const caret = lineEnd < 0 ? text.length : Math.min(text.length, lineEnd + 2);
  $('entryText').setSelectionRange(caret, caret);
}

function insertTemplateAtEnd() {
  const draft = state.newDraft;
  if (!draft || !pendingTemplate) return;
  applyTextChange(appendTemplate(getText(), pendingTemplate.text));
  draft.insertedTemplate = pendingTemplate.text;
  pendingTemplate = null;
  showEndOffer();
  setDirty();
}

// -- Folder ----------------------------------------------------------------

function renderFolderValue() {
  const draft = state.newDraft;
  if (!draft) return;
  const value = $('placementFolderValue');
  value.textContent = draft.folder == null ? 'Not chosen yet' : (draft.folder || 'Vault root');
  value.className = draft.folder == null ? 'is-missing' : '';
}

const vaultKey = () => state.vaultId || window.location.origin;

function rememberFolder(path) {
  if (!path) return;
  const others = storage.readRecentFolders(vaultKey()).filter((item) => item !== path);
  storage.writeRecentFolders(vaultKey(), [path].concat(others));
}

// Called once a draft has been saved in `folder`.
export function noteFolderUsed(folder) {
  rememberFolder(folder);
}

function forgetRecentFolder(path) {
  storage.writeRecentFolders(vaultKey(), storage.readRecentFolders(vaultKey()).filter((item) => item !== path));
  renderRecentFolders();
}

function renderRecentFolders() {
  const host = $('folderRecent');
  const folders = storage.readRecentFolders(vaultKey());
  host.replaceChildren();
  host.hidden = !folders.length;
  if (!folders.length) return;
  host.appendChild(textNode('span', 'Recent:', 'folder-recent-label'));
  folders.forEach((path) => {
    const chip = button(path, '', () => browseFolder(path, true));
    chip.title = 'Use ' + path;
    host.appendChild(chip);
  });
}

function crumb(label, path) {
  return button(label, 'folder-crumb', () => browseFolder(path, true));
}

function renderFolderSelection(path) {
  const draft = state.newDraft;
  const crumbs = h('nav', { class: 'folder-breadcrumbs', 'aria-label': 'Folder path' }, crumb('Vault root', ''));
  let current = '';
  (path || '').split('/').filter(Boolean).forEach((part) => {
    current = current ? current + '/' + part : part;
    crumbs.appendChild(textNode('span', '›', 'folder-crumb-separator'));
    crumbs.appendChild(crumb(part, current));
  });
  const chosen = draft && draft.folder != null ? (draft.folder || 'Vault root') : 'none yet';
  $('folderSelection').replaceChildren(crumbs,
    textNode('span', 'Current destination: ' + chosen, 'folder-destination'));
}

function folderRow(label, icon, onclick) {
  return button([textNode('span', icon, 'folder-browser-icon'), textNode('span', label)], 'folder-browser-row', onclick);
}

function renderFolderBrowser(path, folders, message) {
  const host = $('folderBrowser');
  host.replaceChildren();
  const head = h('div', { class: 'folder-browser-head' }, textNode('span', path ? 'Inside ' + path : 'Vault root'));
  if (path) {
    head.appendChild(folderRow('Up to ' + (folderParent(path) || 'Vault root'), '↥', () => browseFolder(folderParent(path), true)));
  }
  host.appendChild(head);
  if (message) {
    host.appendChild(textNode('p', message, 'folder-browser-empty'));
    return;
  }
  (folders || []).forEach((item) => {
    const target = item.path || ((path ? path + '/' : '') + item.name);
    host.appendChild(folderRow(item.name || item.path, '▸', () => browseFolder(target, true)));
  });
  if (!(folders || []).length) {
    host.appendChild(textNode('p', 'No child folders here. This destination is ready to use.', 'folder-browser-empty'));
  }
}

function childFolders(entries) {
  return (entries || [])
    .filter((item) => item.is_dir)
    .sort((a, b) => (a.name || a.path).localeCompare(b.name || b.path));
}

// Lists `path` in the chooser. With `select` it also becomes the draft's folder.
async function browseFolder(path, select) {
  const draft = state.newDraft;
  const target = path || '';
  const mine = ++folderSequence;
  renderFolderBrowser(folderBrowsing, [], 'Loading folders…');
  try {
    const data = await world.get('/tree', { path: target });
    if (mine !== folderSequence || state.newDraft !== draft || !draft) return;
    state.vaultId = data.vault_id || state.vaultId;
    folderBrowsing = target;
    if (select) {
      draft.folder = target;
      draft.folderSource = 'chosen';
      showIssue('');
      setDirty();
      emit(Events.DRAFT_CHANGED); // the path Nearby reads has moved
      renderFolderValue();
      renderBar();
    }
    renderFolderSelection(target);
    renderFolderBrowser(target, childFolders(data.entries));
    renderRecentFolders();
  } catch (error) {
    if (mine !== folderSequence) return;
    if (target && error.status === 404) forgetRecentFolder(target);
    renderFolderBrowser(folderBrowsing, [], error.message + ' Choose another folder.');
  }
}

async function crawlVaultFolders() {
  if (vaultFoldersLoaded || vaultFoldersLoading) return;
  vaultFoldersLoading = true;
  renderFolderSearch();
  try {
    vaultFolders = (await walkVault()).folders.sort();
    vaultFoldersLoaded = true;
  } catch (_) {
    vaultFolders = [];
  } finally {
    vaultFoldersLoading = false;
    renderFolderSearch();
  }
}

function renderFolderSearch() {
  const query = $('folderSearch').value.trim().toLocaleLowerCase();
  const host = $('folderSearchResults');
  host.replaceChildren();
  if (!query) return;
  if (vaultFoldersLoading) {
    host.appendChild(textNode('p', 'Loading folders…', 'muted'));
    return;
  }
  const matches = vaultFolders.filter((path) => path.toLocaleLowerCase().indexOf(query) >= 0).slice(0, MAX_FOLDER_MATCHES);
  if (!matches.length) {
    host.appendChild(textNode('p', 'No matching folders.', 'muted'));
    return;
  }
  matches.forEach((path) => {
    host.appendChild(button(path, 'create-search-result', () => {
      $('folderSearch').value = '';
      host.replaceChildren();
      browseFolder(path, true);
    }));
  });
}

function openFolderChooser() {
  const draft = state.newDraft;
  if (!draft) return;
  setPanelOpen(true);
  $('placementFolderChooser').hidden = false;
  $('placementFolderToggle').setAttribute('aria-expanded', 'true');
  renderRecentFolders();
  crawlVaultFolders();
  // Listing a folder only browses it; the writer's click is what chooses.
  browseFolder(draft.folder == null ? '' : draft.folder, false);
}

function toggleFolderChooser() {
  if ($('placementFolderChooser').hidden) openFolderChooser();
  else {
    $('placementFolderChooser').hidden = true;
    $('placementFolderToggle').setAttribute('aria-expanded', 'false');
  }
}

// -- The panel -------------------------------------------------------------

function setPanelOpen(open) {
  const was = panelOpen;
  panelOpen = open;
  $('placementPanel').hidden = !open;
  $('placementChange').setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open) {
    if (was) return;
    showPanelNote('');
    renderChosenPlaces();
    renderFolderValue();
    renderKinds();
    loadKinds();
    loadTemplates();
    $('newRepeat').checked = Boolean(state.newDraft && state.newDraft.again);
    showEndOffer();
    // A template chosen earlier but never placed (a reload in between) is offered again.
    if (state.newDraft && state.newDraft.template && !state.newDraft.insertedTemplate) {
      chooseTemplate(state.newDraft.template);
    }
  } else {
    $('placementFolderChooser').hidden = true;
    $('placementFolderToggle').setAttribute('aria-expanded', 'false');
  }
}

// Opens the panel. options.focus is 'folder' or 'place'; options.message a
// one-line reason shown above the fields.
export function openPlacementPanel(options) {
  if (!state.newDraft) return;
  setPanelOpen(true);
  const given = options || {};
  if (given.message) showPanelNote(given.message);
  if (given.focus === 'folder') {
    openFolderChooser();
    $('folderSearch').focus();
  } else if (given.focus === 'place') {
    $('placeSearch').focus();
  }
}

function closePanel() {
  setPanelOpen(false);
  $('placementChange').focus();
}

// Save found something missing: say what, and go to it. A missing title is
// asked for first, in the title field; a missing folder opens the panel on
// the folder chooser with the reason at its top.
export function showMissing(issues) {
  if (issues.title) {
    showIssue(issues.title);
    $('draftTitle').focus();
    return;
  }
  showIssue('');
  openPlacementPanel({ focus: 'folder', message: issues.folder });
}

export function showSaveProblem(message, focusTitle) {
  showIssue(message);
  if (focusTitle) $('draftTitle').focus();
}

export function clearPlacementIssue() {
  showIssue('');
}

// -- Opening and wiring ----------------------------------------------------

// A draft just opened (or came back): reset the panel to match it.
function syncToDraft() {
  const draft = state.newDraft;
  if (!draft) return;
  panelOpen = false;
  suggestedKind = '';
  pendingTemplate = null;
  folderBrowsing = draft.folder || '';
  $('placementPanel').hidden = true;
  $('placementFolderChooser').hidden = true;
  showIssue('');
  showPanelNote('');
  $('draftTitle').value = draft.title;
  $('newRepeat').checked = draft.again;
  $('newTemplate').value = draft.template || '';
  showEndOffer();
  renderBar();
  discardReset();
}

function onTitleInput(event) {
  const draft = state.newDraft;
  if (!draft) return;
  draft.title = event.target.value;
  if (draft.title.trim()) showIssue('');
  setDirty();
  emit(Events.DRAFT_CHANGED); // Nearby reads the draft as <folder>/<title>.md
}

// -- Discarding with an in-page confirmation -------------------------------

function discardReset() {
  $('discardConfirm').hidden = true;
  $('discardDraft').hidden = false;
}

export function initPlacement(handlers) {
  $('placementChange').addEventListener('click', () => (panelOpen ? closePanel() : openPlacementPanel()));
  $('placementClose').addEventListener('click', closePanel);
  $('placementPanel').addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closePanel();
  });
  $('draftTitle').addEventListener('input', onTitleInput);
  $('placeSearch').addEventListener('input', findPlaces);
  $('newTemplate').addEventListener('change', (event) => chooseTemplate(event.target.value));
  $('templateInsertEnd').addEventListener('click', insertTemplateAtEnd);
  $('placementFolderToggle').addEventListener('click', toggleFolderChooser);
  $('folderSearch').addEventListener('input', () => {
    crawlVaultFolders();
    renderFolderSearch();
  });
  $('newRepeat').addEventListener('change', (event) => {
    if (!state.newDraft) return;
    state.newDraft.again = event.target.checked;
    setDirty();
  });
  $('discardDraft').addEventListener('click', () => {
    $('discardDraft').hidden = true;
    $('discardConfirm').hidden = false;
    $('discardKeep').focus();
  });
  $('discardKeep').addEventListener('click', () => {
    discardReset();
    $('discardDraft').focus();
  });
  $('discardYes').addEventListener('click', () => {
    discardReset();
    if (handlers && handlers.discard) handlers.discard();
  });
  on(Events.CREATE_OPENED, syncToDraft);
  on(Events.DRAFT_CHANGED, () => {
    if (state.newDraft) renderBar();
  });
  on(Events.ENTRY_OPENING, () => {
    panelOpen = false;
  });
  on(Events.FOLDER_CREATED, () => {
    vaultFoldersLoaded = false;
    if (state.newDraft && panelOpen && !$('placementFolderChooser').hidden) {
      crawlVaultFolders();
      browseFolder(folderBrowsing, false);
    }
  });
}
