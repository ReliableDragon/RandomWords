import test from 'node:test';
import assert from 'node:assert/strict';

import { DEFAULT_CONFIG, readConfig } from '../static/world/config.js';

function fakeDocument(metas) {
  return {
    querySelector(selector) {
      const match = selector.match(/^meta\[name="([^"]+)"\]$/);
      const name = match && match[1];
      if (!name || !(name in metas)) return null;
      return { getAttribute: (attr) => (attr === 'content' ? metas[name] : null) };
    },
  };
}

test('without a page the defaults preserve the local behavior', () => {
  assert.deepEqual(readConfig(null), DEFAULT_CONFIG);
  assert.equal(DEFAULT_CONFIG.worldApiBase, '/api/world');
  assert.equal(DEFAULT_CONFIG.benchApiBase, '/api');
  assert.equal(DEFAULT_CONFIG.accountScope, 'local');
  assert.equal(DEFAULT_CONFIG.worldScope, 'default');
});

test('a page without the meta tags gives the defaults', () => {
  assert.deepEqual(readConfig(fakeDocument({})), DEFAULT_CONFIG);
});

test('meta tags override each setting', () => {
  const config = readConfig(fakeDocument({
    'rw-world-api': '/api/v1/worlds/abc',
    'rw-bench-api': '/api/v1',
    'rw-account-scope': 'u_7f3a',
    'rw-world-scope': 'abc',
  }));
  assert.deepEqual(config, {
    worldApiBase: '/api/v1/worlds/abc', benchApiBase: '/api/v1',
    accountScope: 'u_7f3a', worldScope: 'abc',
  });
});

test('blank meta values and trailing slashes are cleaned up', () => {
  const config = readConfig(fakeDocument({
    'rw-world-api': '/api/v1/worlds/abc/', 'rw-bench-api': '   ', 'rw-account-scope': '',
  }));
  assert.equal(config.worldApiBase, '/api/v1/worlds/abc');
  assert.equal(config.benchApiBase, '/api');
  assert.equal(config.accountScope, 'local');
});

test('a document that throws falls back to the defaults', () => {
  const broken = { querySelector() { throw new Error('boom'); } };
  assert.deepEqual(readConfig(broken), DEFAULT_CONFIG);
});
