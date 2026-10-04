// Which panel is visible: the desk's panes and the top-level views.
//
// Report views register {load({force}), invalidate()}. Switching to a view
// loads it once; Refresh (or a later change in index generation) calls
// load({force: true}).

import { $ } from './dom.js';
import { Events, on } from './events.js';
import { nextReturnTo, resumesPlace, returnLabel } from './places.js';
import { restoreView, snapshotView } from './report.js';
import { state } from './state.js';

const views = new Map();
let active = 'desk';
// The wide views give the centre the width; Map and Coverage fold the tree away.
const FULL_WIDTH_VIEWS = ['map', 'coverage'];
let filesOpen = false;

// 'desk' keeps three columns, 'wide' drops Nearby, 'full' also folds the tree.
export function layoutFor(name) {
  if (name === 'desk') return 'desk';
  return FULL_WIDTH_VIEWS.indexOf(name) >= 0 ? 'full' : 'wide';
}

export function registerView(name, view) {
  views.set(name, view);
}

export function activeView() {
  return active;
}

function applyLayout() {
  const shell = document.querySelector('.world-shell');
  const layout = layoutFor(active);
  if (shell) {
    shell.setAttribute('data-layout', layout);
    shell.setAttribute('data-tree', layout === 'full' && !filesOpen ? 'rail' : 'open');
  }
  const toggle = $('treeToggle');
  toggle.setAttribute('aria-expanded', layout === 'full' && filesOpen ? 'true' : 'false');
  toggle.textContent = filesOpen ? 'Hide files' : 'Show files';
}

export function toggleFiles() {
  filesOpen = !filesOpen;
  applyLayout();
}

// -- Keeping your place ----------------------------------------------------
//
// Each view keeps its scroll position (the desk also its caret and the text's
// own scroll) while another view is showing, and gets it back on return.

const places = new Map();
// The view the desk's "← Back to …" chip returns to, or null.
let returnTo = null;

const panelFor = (name) => document.querySelector('[data-view-panel="' + name + '"]');

function rememberPlace(name) {
  const panel = panelFor(name);
  const scroller = document.querySelector('.world-editor');
  if (!panel || !scroller) return;
  const inner = snapshotView(panel);
  // The editor and the page are shared by every view and are kept separately.
  inner.scrolls = inner.scrolls.filter((scroll) => scroll.key);
  const place = { editor: scroller.scrollTop, page: window.scrollY || 0, inner };
  const field = name === 'desk' ? $('entryText') : null;
  if (field) {
    place.caret = { start: field.selectionStart, end: field.selectionEnd, top: field.scrollTop };
  }
  places.set(name, place);
}

function applyPlace(name, place) {
  const scroller = document.querySelector('.world-editor');
  if (scroller) scroller.scrollTop = place ? place.editor : 0;
  if (window.scrollTo) window.scrollTo(0, place ? place.page : 0);
  if (!place) return;
  const panel = panelFor(name);
  if (panel) restoreView(panel, place.inner);
  const field = place.caret ? $('entryText') : null;
  if (field && field.setSelectionRange) {
    const length = (field.value || '').length;
    // The text may have changed under a saved caret; keep it inside.
    field.setSelectionRange(Math.min(place.caret.start, length), Math.min(place.caret.end, length));
    field.scrollTop = place.caret.top;
  }
}

// Reports that load in the background draw after the switch, so the place is
// put back once more when they finish.
function restorePlace(name, loading) {
  const place = places.get(name);
  applyPlace(name, place);
  Promise.resolve(loading).then(() => {
    if (active === name) applyPlace(name, place);
  }, () => {});
}

function renderReturnChip() {
  const bar = $('returnBar');
  if (!bar) return;
  bar.hidden = !returnTo;
  if (returnTo) $('returnChip').textContent = returnLabel(returnTo);
}

// The view the desk's back chip points at (null when there is none).
export function returnTarget() {
  return returnTo;
}

// Shows the Desk tab's dot while the open draft has unsaved changes.
export function setDeskUnsaved(unsaved) {
  const dot = $('deskDot');
  if (dot) dot.hidden = !unsaved;
}

// Switches the visible view. options.via is 'tab' when the writer chose it
// from the tabs (or the back chip); anything else is a view sending them on.
export function setWorldView(name, options) {
  const from = active;
  const via = options && options.via;
  if (from !== name) rememberPlace(from);
  returnTo = nextReturnTo({ from, to: name, via, current: returnTo });
  active = name;
  applyLayout();
  document.querySelectorAll('[data-view-panel]').forEach((panel) => {
    panel.hidden = panel.getAttribute('data-view-panel') !== name;
  });
  document.querySelectorAll('[data-world-view]').forEach((button) => {
    if (button.getAttribute('data-world-view') === name) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  renderReturnChip();
  const view = views.get(name);
  const loading = view ? view.load() : null;
  if (from === name) return;
  if (resumesPlace({ from, to: name, via })) restorePlace(name, loading);
  else applyPlace(name, null);
}

// Reloads a view now if it is showing, otherwise on its next visit.
export function refreshView(name) {
  const view = views.get(name);
  if (!view) return;
  if (active === name) view.load({ force: true });
  else if (view.invalidate) view.invalidate();
}

export function invalidateView(name) {
  const view = views.get(name);
  if (view && view.invalidate) view.invalidate();
}

// Inside the desk view: the welcome text or the editor (an entry, or a new draft).
export function showPane(which) {
  $('welcome').hidden = which !== 'welcome';
  $('entryPane').hidden = which !== 'entry';
  setDeskUnsaved(Boolean(state.dirty));
  if (which === 'welcome') welcomeListeners.forEach((listener) => listener());
}

// Calls `listener` each time the welcome text is shown again.
const welcomeListeners = [];

export function onWelcomeShown(listener) {
  welcomeListeners.push(listener);
}

export function initNav() {
  $('treeToggle').addEventListener('click', toggleFiles);
  const syncDot = () => setDeskUnsaved(Boolean(state.dirty));
  on(Events.DRAFT_CHANGED, syncDot);
  on(Events.ENTRY_OPENED, syncDot);
  applyLayout();
  document.querySelectorAll('[data-world-view]').forEach((button) => {
    button.addEventListener('click', () => setWorldView(button.getAttribute('data-world-view'), { via: 'tab' }));
  });
  const chip = $('returnChip');
  if (chip) chip.addEventListener('click', () => { if (returnTo) setWorldView(returnTo, { via: 'tab' }); });
  document.querySelectorAll('[data-refresh-view]').forEach((button) => {
    button.addEventListener('click', () => {
      const view = views.get(button.dataset.refreshView);
      if (view) view.load({ force: true });
    });
  });
}
