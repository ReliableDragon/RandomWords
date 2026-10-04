import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

import { installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

globalThis.setTimeout = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setTimeout);

const drawer = await import('../static/world/generator_drawer.js');
const bench = await import('../static/world/bench.js');

test('isEmbedSearch only accepts embed=1 as a whole parameter', () => {
  assert.equal(drawer.isEmbedSearch('?embed=1'), true);
  assert.equal(drawer.isEmbedSearch('embed=1'), true);
  assert.equal(drawer.isEmbedSearch('?a=b&embed=1&c=d'), true);
  assert.equal(drawer.isEmbedSearch(''), false);
  assert.equal(drawer.isEmbedSearch('?embed=0'), false);
  assert.equal(drawer.isEmbedSearch('?embed=10'), false);
  assert.equal(drawer.isEmbedSearch('?notembed=1'), false);
  assert.equal(drawer.isEmbedSearch(undefined), false);
  assert.equal(drawer.EMBED_URL, '/?embed=1');
});

// The generator page marks itself with /embed.js, which has to agree with isEmbedSearch.
test('embed.js sets data-embed for ?embed=1 and for nothing else', () => {
  const html = fs.readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
  assert.ok(html.includes('<script src="/embed.js"></script>'), 'index.html loads /embed.js');
  const script = fs.readFileSync(new URL('../static/embed.js', import.meta.url), 'utf8');
  ['?embed=1', '?x=1&embed=1', '', '?embed=0', '?embed=11', '?xembed=1'].forEach((search) => {
    const attrs = new Map();
    const context = {
      location: { search },
      document: { documentElement: { setAttribute: (name) => attrs.set(name, '') } },
    };
    vm.runInNewContext(script, context);
    assert.equal(attrs.has('data-embed'), drawer.isEmbedSearch(search), 'search ' + JSON.stringify(search));
  });
});

test('the embedded page hides the header links and never fetches the world link', () => {
  const css = fs.readFileSync(new URL('../static/app.css', import.meta.url), 'utf8');
  ['.brand', '#walkthroughLink', '#worldLink'].forEach((selector) => {
    assert.ok(css.includes('html[data-embed] ' + selector), selector);
  });
});

test('sameWords, closesOnKey and isCloseMessage', () => {
  assert.equal(drawer.sameWords(['a', 'b'], ['a', 'b']), true);
  assert.equal(drawer.sameWords(['a', 'b'], ['b', 'a']), false);
  assert.equal(drawer.sameWords([], ['a']), false);
  assert.equal(drawer.closesOnKey({ key: 'Escape' }, true), true);
  assert.equal(drawer.closesOnKey({ key: 'Escape' }, false), false);
  assert.equal(drawer.closesOnKey({ key: 'a' }, true), false);
  const win = {};
  const good = { origin: 'http://x', source: win, data: { type: drawer.CLOSE_MESSAGE } };
  assert.equal(drawer.isCloseMessage(good, win, 'http://x'), true);
  assert.equal(drawer.isCloseMessage({ ...good, origin: 'http://evil' }, win, 'http://x'), false);
  assert.equal(drawer.isCloseMessage({ ...good, source: {} }, win, 'http://x'), false);
  assert.equal(drawer.isCloseMessage({ ...good, data: { type: 'other' } }, win, 'http://x'), false);
  assert.equal(drawer.isCloseMessage({ ...good, data: null }, win, 'http://x'), false);
});

function setup(initialKept) {
  const dom = installFakeDom();
  const $ = (id) => dom.document.getElementById(id);
  const store = new Map();
  if (initialKept) store.set('randomwords.kept.v1', JSON.stringify({ v: 1, words: initialKept }));
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); }, key: (i) => Array.from(store.keys())[i], get length() { return store.size; },
  };
  const windowListeners = new Map();
  globalThis.window.addEventListener = (type, fn) => {
    if (!windowListeners.has(type)) windowListeners.set(type, []);
    windowListeners.get(type).push(fn);
  };
  ['benchStrip', 'main'].forEach((name) => dom.document.body.appendChild($(name)));
  dom.document.body.appendChild($('generatorDrawer'));
  $('generatorDrawer').hidden = true;
  const fire = (type, event) => (windowListeners.get(type) || []).forEach((fn) => fn(event));
  return { dom, $, store, fire };
}

function teardown() {
  uninstallFakeDom();
  delete globalThis.fetch;
  delete globalThis.localStorage;
}

test('the drawer loads the frame once, on first open, and keeps it afterwards', () => {
  const { dom, $ } = setup();
  try {
    let closed = 0;
    const api = drawer.initGeneratorDrawer({ onClose: () => { closed += 1; } });
    assert.equal(api.frame(), null);
    assert.equal($('generatorDrawer').hidden, true);
    $('openGenerator').click();
    assert.equal($('generatorDrawer').hidden, false);
    const frame = api.frame();
    assert.equal(frame.getAttribute('src'), '/?embed=1');
    assert.equal(frame.getAttribute('title'), 'Word generator');
    assert.equal($('openGenerator').getAttribute('aria-expanded'), 'true');
    // Everything but the drawer goes inert while it is open.
    assert.equal($('benchStrip').getAttribute('inert'), '');
    assert.equal($('generatorDrawer').getAttribute('inert'), null);
    $('closeGenerator').click();
    assert.equal($('generatorDrawer').hidden, true);
    assert.equal($('benchStrip').getAttribute('inert'), null);
    assert.equal($('openGenerator').getAttribute('aria-expanded'), 'false');
    assert.equal(closed, 1);
    $('openGenerator').click();
    assert.equal(api.frame(), frame);
    assert.equal($('generatorFrameHost').children.length, 1);
    // Esc on the desk closes it; Esc while it is already closed does nothing.
    (dom.listeners.get('keydown') || []).forEach((fn) => fn({ key: 'Escape', preventDefault() {} }));
    assert.equal($('generatorDrawer').hidden, true);
    assert.equal(closed, 2);
    (dom.listeners.get('keydown') || []).forEach((fn) => fn({ key: 'Escape', preventDefault() {} }));
    assert.equal(closed, 2);
    // The scrim closes it too.
    $('openGenerator').click();
    $('generatorScrim').click();
    assert.equal($('generatorDrawer').hidden, true);
    assert.equal(closed, 3);
  } finally {
    teardown();
  }
});

test('a close message from the framed generator closes the drawer; one from elsewhere does not', () => {
  const { $, fire } = setup();
  try {
    const api = drawer.initGeneratorDrawer({});
    $('openGenerator').click();
    const frameWindow = {};
    api.frame().contentWindow = frameWindow;
    fire('message', { origin: 'http://evil', source: frameWindow, data: { type: drawer.CLOSE_MESSAGE } });
    assert.equal(api.isOpen(), true);
    fire('message', { origin: location.origin, source: {}, data: { type: drawer.CLOSE_MESSAGE } });
    assert.equal(api.isOpen(), true);
    fire('message', { origin: location.origin, source: frameWindow, data: { type: drawer.CLOSE_MESSAGE } });
    assert.equal(api.isOpen(), false);
  } finally {
    teardown();
  }
});

test('a word kept in the generator reaches the bench on a storage event and again on close', () => {
  const { $, store, fire } = setup(['moss']);
  installFakeFetch({});
  try {
    bench.initBench();
    assert.equal($('benchSummary').textContent, '1 kept: moss');
    // The drawer's generator keeps "loam" by writing the shared key.
    store.set('randomwords.kept.v1', JSON.stringify({ v: 1, words: ['moss', 'loam'] }));
    fire('storage', { key: 'randomwords.kept.v1' });
    assert.equal($('benchSummary').textContent, '2 kept: moss, loam');
    assert.equal($('startFromKept').disabled, false);
    // Closing re-reads too, in case the event was missed.
    store.set('randomwords.kept.v1', JSON.stringify({ v: 1, words: ['moss', 'loam', 'reed'] }));
    $('openGenerator').click();
    $('closeGenerator').click();
    assert.equal($('benchSummary').textContent, '3 kept: moss, loam, reed');
    // Re-reading never writes: the stored list is exactly what the generator wrote.
    assert.equal(store.get('randomwords.kept.v1'), JSON.stringify({ v: 1, words: ['moss', 'loam', 'reed'] }));
    // Nothing changed: no re-render.
    assert.equal(bench.syncKeptFromStorage(), false);
  } finally {
    teardown();
  }
});
