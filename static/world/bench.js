// The word bench strip: draw words, keep the ones that spark.

import { bench } from './api.js';
import { $, button, h, setStatus, textNode } from './dom.js';
import { openCreate } from './create.js';
import { emit, Events } from './events.js';
import { initGeneratorDrawer, sameWords } from './generator_drawer.js';
import { state } from './state.js';
import { storage } from './storage.js';

const DEFAULT_DRAW = 3;
const MAX_DRAW = 20;

function toggleKept(word) {
  const at = state.kept.indexOf(word);
  if (at >= 0) state.kept.splice(at, 1);
  else state.kept.push(word);
  renderBench();
}

function drawnWord(word) {
  const isKept = state.kept.indexOf(word) >= 0;
  const node = button(word, 'bench-word' + (isKept ? ' is-kept' : ''), () => toggleKept(word));
  node.title = isKept ? 'Remove from kept' : 'Keep word';
  return node;
}

// A kept word that was not in the last draw can only be removed.
function keptOnlyWord(word) {
  const node = button(word, 'bench-word is-kept', () => {
    state.kept = state.kept.filter((other) => other !== word);
    renderBench();
  });
  node.title = 'Remove from kept';
  return node;
}

// -- Collapsing the strip to a one-line bar ---------------------------------

const COLLAPSE_PREF = 'benchCollapsed';
const SHORT_SCREEN = '(max-height: 720px)';

// No saved choice: short screens start collapsed so the strip does not eat the editor.
function initiallyCollapsed() {
  const saved = storage.readPref(COLLAPSE_PREF);
  if (typeof saved === 'boolean') return saved;
  return typeof window.matchMedia === 'function' && window.matchMedia(SHORT_SCREEN).matches;
}

function keptSummary() {
  if (!state.kept.length) return 'nothing kept yet';
  const shown = state.kept.slice(0, 4).join(', ');
  return state.kept.length + ' kept: ' + shown + (state.kept.length > 4 ? '…' : '');
}

function renderSummary() {
  const node = $('benchSummary');
  node.textContent = keptSummary();
}

export function setBenchCollapsed(collapsed, options) {
  const strip = $('benchStrip');
  strip.classList.toggle('is-collapsed', collapsed);
  $('benchBody').hidden = collapsed;
  $('benchSummary').hidden = !collapsed;
  const toggle = $('benchToggle');
  toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  toggle.textContent = collapsed ? 'Show bench' : 'Hide bench';
  if (!options || options.persist !== false) storage.writePref(COLLAPSE_PREF, collapsed);
}

function renderBench(options) {
  if (!options || options.persist !== false) storage.writeKept(state.kept);
  const host = $('benchWords');
  host.replaceChildren();
  if (!state.drawn.length && !state.kept.length) {
    host.appendChild(textNode('span', 'Draw some words, then keep the ones you want to use.', 'muted'));
  }
  state.drawn.forEach((word) => host.appendChild(drawnWord(word)));
  state.kept.filter((word) => state.drawn.indexOf(word) < 0)
    .forEach((word) => host.appendChild(keptOnlyWord(word)));
  emit(Events.KEPT_CHANGED);
  $('startFromKept').disabled = !state.kept.length;
  renderSummary();
}

// Re-reads kept words from storage, e.g. after the generator drawer kept one.
// Never writes back, so two pages cannot ping-pong the same list.
//
// Local-mode convenience: the two pages share one localStorage key. Hosted
// mode will move kept words to server bench state (HOSTING_DESIGN.md), and
// this sync will then come from the bench API instead of the storage event.
export function syncKeptFromStorage() {
  const saved = storage.readKept();
  if (sameWords(saved, state.kept)) return false;
  state.kept = saved;
  renderBench({ persist: false });
  return true;
}

async function drawWords() {
  const count = Math.max(1, Math.min(MAX_DRAW, parseInt($('drawCount').value, 10) || DEFAULT_DRAW));
  try {
    const data = await bench.post('/draw', { count });
    state.drawn = data.drawn || [];
    renderBench();
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

async function loadPools() {
  try {
    const data = await bench.get('/pools');
    const select = $('benchPool');
    (data.pools || []).forEach((pool) => {
      select.appendChild(h('option', { value: pool.path || pool.name }, pool.name || pool.path));
    });
  } catch (_) {
    // The static pool choices stay usable without the list.
  }
}

async function choosePool(event) {
  const source = event.target.value;
  if (!source) return;
  try {
    await bench.post('/pools/load', { source });
    setStatus('Loaded ' + source, 'ready');
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

export function initBench() {
  state.kept = storage.readKept();
  $('drawWords').addEventListener('click', drawWords);
  $('startFromKept').addEventListener('click', () => openCreate());
  $('clearKept').addEventListener('click', () => {
    state.kept = [];
    renderBench();
  });
  $('benchPool').addEventListener('change', choosePool);
  // Keeps arriving from the generator, which is a separate page.
  window.addEventListener('storage', syncKeptFromStorage);
  initGeneratorDrawer({ onClose: syncKeptFromStorage });
  $('benchToggle').addEventListener('click', () => {
    setBenchCollapsed(!$('benchStrip').classList.contains('is-collapsed'));
  });
  setBenchCollapsed(initiallyCollapsed(), { persist: false });
  renderBench({ persist: false });
  loadPools();
}
