import test from 'node:test';
import assert from 'node:assert/strict';

import { installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

globalThis.setTimeout = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setTimeout);
globalThis.setInterval = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setInterval);

const nav = await import('../static/world/nav.js');
const bench = await import('../static/world/bench.js');
const { createStorage } = await import('../static/world/storage.js');

test('layoutFor: Desk keeps three columns, Map and Coverage fold the tree, the rest drop Nearby', () => {
  assert.equal(nav.layoutFor('desk'), 'desk');
  ['map', 'coverage'].forEach((name) => assert.equal(nav.layoutFor(name), 'full'));
  ['story', 'upkeep', 'lexicon', 'backlog'].forEach((name) => assert.equal(nav.layoutFor(name), 'wide'));
});

test('switching views sets the shell layout; the Show files button opens the rail and it resets', () => {
  const dom = installFakeDom();
  const shell = dom.document.getElementById('shell');
  dom.document.querySelector = (selector) => (selector === '.world-shell' ? shell : null);
  const toggle = dom.document.getElementById('treeToggle');
  try {
    nav.initNav();
    assert.equal(shell.getAttribute('data-layout'), 'desk');
    assert.equal(shell.getAttribute('data-tree'), 'open');
    nav.setWorldView('story');
    assert.equal(shell.getAttribute('data-layout'), 'wide');
    assert.equal(shell.getAttribute('data-tree'), 'open');
    nav.setWorldView('map');
    assert.equal(shell.getAttribute('data-layout'), 'full');
    assert.equal(shell.getAttribute('data-tree'), 'rail');
    assert.equal(toggle.textContent, 'Show files');
    toggle.click();
    assert.equal(shell.getAttribute('data-tree'), 'open');
    assert.equal(toggle.textContent, 'Hide files');
    assert.equal(toggle.getAttribute('aria-expanded'), 'true');
    toggle.click();
    assert.equal(shell.getAttribute('data-tree'), 'rail');
    assert.equal(toggle.getAttribute('aria-expanded'), 'false');
    nav.setWorldView('desk');
    assert.equal(shell.getAttribute('data-layout'), 'desk');
    assert.equal(shell.getAttribute('data-tree'), 'open');
  } finally {
    uninstallFakeDom();
  }
});

function memoryBackend(initial) {
  const data = new Map(Object.entries(initial || {}));
  return {
    data,
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => { data.set(k, String(v)); },
    removeItem: (k) => { data.delete(k); },
    keys: () => Array.from(data.keys()),
  };
}

test('preferences round-trip through storage and survive a broken backend', () => {
  const backend = memoryBackend();
  const store = createStorage({ backend });
  assert.equal(store.readPref('benchCollapsed'), null);
  store.writePref('benchCollapsed', true);
  assert.equal(store.readPref('benchCollapsed'), true);
  assert.deepEqual(backend.keys(), ['rw:v2:local:default:pref:benchCollapsed']);
  const broken = createStorage({ backend: { getItem() { throw new Error('no'); }, setItem() { throw new Error('no'); }, removeItem() {}, keys: () => [] } });
  assert.equal(broken.readPref('x'), null);
  assert.equal(broken.writePref('x', 1), false);
});

test('the bench collapses to a one-line bar, says what is kept, and remembers the choice', async () => {
  const dom = installFakeDom();
  const $ = (id) => dom.document.getElementById(id);
  const backend = memoryBackend({ 'randomwords.kept.v1': JSON.stringify({ v: 1, words: ['moss', 'loam'] }) });
  globalThis.localStorage = {
    getItem: (k) => backend.getItem(k), setItem: (k, v) => backend.setItem(k, v),
    removeItem: (k) => backend.removeItem(k), key: (i) => backend.keys()[i], get length() { return backend.keys().length; },
  };
  installFakeFetch({});
  try {
    bench.initBench();
    // No saved choice on a screen without matchMedia: the bench starts open.
    assert.equal($('benchBody').hidden, false);
    assert.equal($('benchStrip').classList.contains('is-collapsed'), false);
    $('benchToggle').click();
    assert.equal($('benchBody').hidden, true);
    assert.equal($('benchStrip').classList.contains('is-collapsed'), true);
    assert.equal($('benchToggle').getAttribute('aria-expanded'), 'false');
    assert.equal($('benchToggle').textContent, 'Show bench');
    assert.equal($('benchSummary').hidden, false);
    assert.equal($('benchSummary').textContent, '2 kept: moss, loam');
    assert.equal(backend.getItem('rw:v2:local:default:pref:benchCollapsed'), 'true');
    // A later visit starts collapsed.
    bench.setBenchCollapsed(false, { persist: false });
    assert.equal($('benchBody').hidden, false);
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
    delete globalThis.localStorage;
  }
});
