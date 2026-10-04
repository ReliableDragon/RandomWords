import test from 'node:test';
import assert from 'node:assert/strict';

import { findAll, installFakeDom, installFakeFetch, uninstallFakeDom } from './fake_dom.mjs';

globalThis.setTimeout = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setTimeout);
globalThis.setInterval = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setInterval);

const tree = await import('../static/world/tree.js');
const { emit, Events } = await import('../static/world/events.js');
const { state } = await import('../static/world/state.js');

const settle = (ms) => new Promise((resolve) => setTimeout(resolve, ms || 0));
const ok = (data) => ({ body: { ok: true, data } });

function listing(words) {
  return (call) => {
    const path = new URL(call.url, 'http://x').searchParams.get('path') || '';
    if (path === '') return ok({ vault_id: 'v', entries: [
      { name: 'People', path: 'People', is_dir: true }, { name: 'Places', path: 'Places', is_dir: true }] });
    if (path === 'Places') return ok({ entries: [{ name: 'Harbors', path: 'Places/Harbors', is_dir: true }] });
    if (path === 'Places/Harbors') {
      const entries = [{ path: 'Places/Harbors/Reed.md', title: 'Reed', words: words.reed }];
      if (words.extra) entries.push({ path: 'Places/Harbors/Sedge.md', title: 'Sedge', words: 3 });
      return ok({ entries });
    }
    return ok({ entries: [{ path: 'People/Ada.md', title: 'Ada', words: 5 }] });
  };
}

const rowOf = (root, path) => findAll(root, (n) => n.getAttribute('data-path') === path)[0];

test('the tree opens the ancestors of the opened entry and marks its row', async () => {
  const dom = installFakeDom();
  const words = { reed: 10 };
  const calls = installFakeFetch({ 'GET /api/world/tree': listing(words) });
  const root = dom.document.getElementById('worldTree');
  let off = () => {};
  try {
    off = tree.initTree();
    await tree.loadRoot();
    assert.equal(rowOf(root, 'Places').getAttribute('aria-expanded'), 'false');
    assert.equal(rowOf(root, 'Places/Harbors'), undefined);

    state.current = 'Places/Harbors/Reed.md';
    emit(Events.ENTRY_OPENED, { path: 'Places/Harbors/Reed.md', title: 'Reed' });
    await settle(30);
    assert.equal(rowOf(root, 'Places').getAttribute('aria-expanded'), 'true');
    assert.equal(rowOf(root, 'Places/Harbors').getAttribute('aria-expanded'), 'true');
    const reed = rowOf(root, 'Places/Harbors/Reed.md');
    assert.equal(reed.getAttribute('aria-current'), 'true');
    assert.equal(reed.classList.contains('is-selected'), true);
    assert.equal(reed.querySelector('.tree-count').textContent, '10');

    // Opening another entry moves the mark and leaves the open folders alone.
    await tree.refreshFolder('People');
    const before = calls.length;
    state.current = 'Places/Harbors/Reed.md';
    emit(Events.ENTRY_OPENED, { path: 'Places/Harbors/Reed.md' });
    await settle(30);
    assert.equal(findAll(root, (n) => n.getAttribute('aria-current') === 'true').length, 1);
    // One request refreshes the entry's folder; nothing else is reloaded.
    assert.equal(calls.length - before, 1);
  } finally {
    off();
    uninstallFakeDom();
    delete globalThis.fetch;
  }
});

test('a save refreshes the affected folder: counts in place, new entries as rows', async () => {
  const dom = installFakeDom();
  const words = { reed: 10 };
  installFakeFetch({ 'GET /api/world/tree': listing(words) });
  const root = dom.document.getElementById('worldTree');
  let off = () => {};
  try {
    off = tree.initTree();
    state.current = 'Places/Harbors/Reed.md';
    await tree.loadRoot();
    emit(Events.ENTRY_OPENED, { path: 'Places/Harbors/Reed.md' });
    await settle(30);
    const reed = rowOf(root, 'Places/Harbors/Reed.md');
    words.reed = 42;
    emit(Events.VAULT_CHANGED, { generation: 2, path: 'Places/Harbors/Reed.md' });
    await settle(30);
    assert.equal(rowOf(root, 'Places/Harbors/Reed.md'), reed, 'the row was updated, not rebuilt');
    assert.equal(reed.querySelector('.tree-count').textContent, '42');

    words.extra = true;
    emit(Events.VAULT_CHANGED, { generation: 3, path: 'Places/Harbors/Sedge.md' });
    await settle(30);
    assert.ok(rowOf(root, 'Places/Harbors/Sedge.md'));
    assert.equal(rowOf(root, 'Places/Harbors/Reed.md').getAttribute('aria-current'), 'true');
  } finally {
    off();
    uninstallFakeDom();
    delete globalThis.fetch;
  }
});

test('collapsing a folder by hand still works and updates aria-expanded', async () => {
  const dom = installFakeDom();
  installFakeFetch({ 'GET /api/world/tree': listing({ reed: 1 }) });
  const root = dom.document.getElementById('worldTree');
  try {
    state.current = null;
    await tree.loadRoot();
    let places = rowOf(root, 'Places');
    // Earlier tests left Places open (open folders are remembered): close it first.
    if (places.getAttribute('aria-expanded') === 'true') {
      places.click();
      await settle(5);
    }
    assert.equal(places.getAttribute('aria-expanded'), 'false');
    places.click();
    await settle(20);
    assert.equal(places.getAttribute('aria-expanded'), 'true');
    assert.ok(rowOf(root, 'Places/Harbors'));
    places.click();
    await settle(5);
    assert.equal(places.getAttribute('aria-expanded'), 'false');
    assert.equal(rowOf(root, 'Places/Harbors'), undefined);
  } finally {
    uninstallFakeDom();
    delete globalThis.fetch;
  }
});
