import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createStorage, scopeKey, LEGACY_PREFIX, LEGACY_KEPT_KEY,
} from '../static/world/storage.js';

// A stand-in for localStorage that can be told to fail.
function fakeBackend(initial) {
  const data = new Map(Object.entries(initial || {}));
  const backend = {
    data,
    failWrites: false,
    failAll: false,
    getItem(key) {
      if (backend.failAll) throw new Error('storage disabled');
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      if (backend.failAll || backend.failWrites) throw new Error('quota');
      data.set(key, String(value));
    },
    removeItem(key) {
      if (backend.failAll) throw new Error('storage disabled');
      data.delete(key);
    },
    keys() {
      if (backend.failAll) throw new Error('storage disabled');
      return Array.from(data.keys());
    },
  };
  return backend;
}

const draft = { text: 'unsaved words', revision: 'r1', updated: '2026-09-28T10:00:00.000Z' };
const legacyDraftKey = LEGACY_PREFIX.draft + 'People/Ada.md';
const newDraftKey = scopeKey('local', 'default', 'draft', 'People/Ada.md');

test('scoped keys separate accounts and worlds', () => {
  const a = scopeKey('u1', 'w1', 'draft', 'x.md');
  assert.notEqual(a, scopeKey('u2', 'w1', 'draft', 'x.md'));
  assert.notEqual(a, scopeKey('u1', 'w2', 'draft', 'x.md'));
  assert.notEqual(a, scopeKey('u1', 'w1', 'recovery', 'x.md'));
  assert.ok(a.endsWith(':x.md'));
});

test('scope values containing separators cannot alias another scope', () => {
  assert.notEqual(scopeKey('a:b', 'c', 'draft', 'x'), scopeKey('a', 'b:c', 'draft', 'x'));
});

test('a legacy draft is read, migrated to the new key, and the old key removed', () => {
  const backend = fakeBackend({ [legacyDraftKey]: JSON.stringify(draft) });
  const storage = createStorage({ backend });
  assert.deepEqual(storage.readDraft('People/Ada.md'), draft);
  assert.equal(backend.data.has(legacyDraftKey), false);
  assert.deepEqual(JSON.parse(backend.data.get(newDraftKey)), draft);
  // A second read comes from the new key.
  assert.deepEqual(storage.readDraft('People/Ada.md'), draft);
});

test('the legacy key is kept when the copy to the new key fails', () => {
  const backend = fakeBackend({ [legacyDraftKey]: JSON.stringify(draft) });
  backend.failWrites = true;
  const storage = createStorage({ backend });
  assert.deepEqual(storage.readDraft('People/Ada.md'), draft);
  assert.ok(backend.data.has(legacyDraftKey), 'draft must not be lost');
  assert.equal(backend.data.has(newDraftKey), false);
});

test('a legacy draft that is not valid JSON is moved but reads as absent', () => {
  const backend = fakeBackend({ [legacyDraftKey]: '{not json' });
  const storage = createStorage({ backend });
  assert.equal(storage.readDraft('People/Ada.md'), null);
  assert.equal(backend.data.get(newDraftKey), '{not json');
});

test('the new key wins over a legacy one', () => {
  const backend = fakeBackend({
    [legacyDraftKey]: JSON.stringify({ text: 'old' }),
    [newDraftKey]: JSON.stringify({ text: 'new' }),
  });
  assert.equal(createStorage({ backend }).readDraft('People/Ada.md').text, 'new');
});

test('writing a draft writes the new key and clears the legacy copy', () => {
  const backend = fakeBackend({ [legacyDraftKey]: JSON.stringify({ text: 'old' }) });
  const storage = createStorage({ backend });
  assert.equal(storage.writeDraft('People/Ada.md', draft), true);
  assert.deepEqual(JSON.parse(backend.data.get(newDraftKey)), draft);
  assert.equal(backend.data.has(legacyDraftKey), false);
});

test('removing a draft removes both keys so a stale legacy draft cannot return', () => {
  const backend = fakeBackend({
    [legacyDraftKey]: JSON.stringify({ text: 'old' }),
    [newDraftKey]: JSON.stringify({ text: 'new' }),
  });
  const storage = createStorage({ backend });
  storage.removeDraft('People/Ada.md');
  assert.equal(storage.readDraft('People/Ada.md'), null);
  assert.equal(backend.data.size, 0);
});

test('recoveries migrate the same way', () => {
  const legacy = LEGACY_PREFIX.recovery + 'A.md';
  const backend = fakeBackend({ [legacy]: JSON.stringify({ text: 'kept', recoveredAt: 'now' }) });
  const storage = createStorage({ backend });
  assert.equal(storage.readRecovery('A.md').text, 'kept');
  assert.equal(backend.data.has(legacy), false);
  assert.ok(backend.data.has(scopeKey('local', 'default', 'recovery', 'A.md')));
  storage.removeRecovery('A.md');
  assert.equal(storage.readRecovery('A.md'), null);
});

test('recent folders migrate, keep the vault suffix, and stay capped and filtered', () => {
  const legacy = LEGACY_PREFIX.recentFolders + 'vault-1';
  const folders = ['A', 'B', '', 7, 'C', 'D', 'E', 'F', 'G', 'H', 'I'];
  const backend = fakeBackend({ [legacy]: JSON.stringify({ v: 1, folders }) });
  const storage = createStorage({ backend });
  assert.deepEqual(storage.readRecentFolders('vault-1'), ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']);
  assert.equal(backend.data.has(legacy), false);
  assert.deepEqual(storage.readRecentFolders('other-vault'), []);
  storage.writeRecentFolders('vault-1', ['Z', 'A']);
  assert.deepEqual(storage.readRecentFolders('vault-1'), ['Z', 'A']);
});

test('recent folders ignore unknown formats', () => {
  const backend = fakeBackend({
    [scopeKey('local', 'default', 'recent-folders', 'v')]: JSON.stringify({ v: 2, folders: ['A'] }),
  });
  assert.deepEqual(createStorage({ backend }).readRecentFolders('v'), []);
});

test('outside the default scope the legacy keys are never read or touched', () => {
  const backend = fakeBackend({ [legacyDraftKey]: JSON.stringify(draft) });
  const storage = createStorage({ backend, accountScope: 'u_1', worldScope: 'w_1' });
  assert.equal(storage.readDraft('People/Ada.md'), null);
  assert.ok(backend.data.has(legacyDraftKey), 'another account must not consume local drafts');
  storage.writeDraft('People/Ada.md', { text: 'mine' });
  storage.removeDraft('People/Ada.md');
  assert.ok(backend.data.has(legacyDraftKey));
});

test('two accounts do not see each other\'s drafts', () => {
  const backend = fakeBackend();
  const one = createStorage({ backend, accountScope: 'u1', worldScope: 'w' });
  const two = createStorage({ backend, accountScope: 'u2', worldScope: 'w' });
  one.writeDraft('A.md', { text: 'private' });
  assert.equal(two.readDraft('A.md'), null);
  assert.equal(one.readDraft('A.md').text, 'private');
});

test('every access is guarded when storage throws', () => {
  const backend = fakeBackend({ [legacyDraftKey]: JSON.stringify(draft) });
  backend.failAll = true;
  const storage = createStorage({ backend });
  assert.equal(storage.readDraft('People/Ada.md'), null);
  assert.equal(storage.writeDraft('People/Ada.md', draft), false);
  assert.doesNotThrow(() => storage.removeDraft('People/Ada.md'));
  assert.deepEqual(storage.readRecentFolders('v'), []);
  assert.equal(storage.writeRecentFolders('v', ['A']), false);
  assert.deepEqual(storage.readKept(), []);
  assert.equal(storage.writeKept(['x']), false);
  assert.doesNotThrow(() => storage.clearAccount());
});

test('kept words stay on the key the word-bench page shares in the local scope', () => {
  const backend = fakeBackend({ [LEGACY_KEPT_KEY]: JSON.stringify({ v: 1, words: ['loam', 3, 'rain'] }) });
  const storage = createStorage({ backend });
  assert.deepEqual(storage.readKept(), ['loam', 'rain']);
  storage.writeKept(['loam']);
  assert.deepEqual(JSON.parse(backend.data.get(LEGACY_KEPT_KEY)), { v: 1, words: ['loam'] });
  assert.equal(backend.data.size, 1, 'no scoped copy is made');
});

test('kept words are scoped per account outside the local scope', () => {
  const backend = fakeBackend({ [LEGACY_KEPT_KEY]: JSON.stringify({ v: 1, words: ['local'] }) });
  const storage = createStorage({ backend, accountScope: 'u1' });
  assert.deepEqual(storage.readKept(), []);
  storage.writeKept(['mine']);
  assert.deepEqual(storage.readKept(), ['mine']);
  assert.ok(backend.data.has(LEGACY_KEPT_KEY));
});

test('clearAccount removes only that account\'s keys', () => {
  const backend = fakeBackend();
  const one = createStorage({ backend, accountScope: 'u1', worldScope: 'w1' });
  const oneOther = createStorage({ backend, accountScope: 'u1', worldScope: 'w2' });
  const two = createStorage({ backend, accountScope: 'u2', worldScope: 'w1' });
  one.writeDraft('A.md', { text: 'a' });
  oneOther.writeDraft('A.md', { text: 'b' });
  two.writeDraft('A.md', { text: 'c' });
  backend.data.set('unrelated', 'x');
  one.clearAccount();
  assert.equal(one.readDraft('A.md'), null);
  assert.equal(oneOther.readDraft('A.md'), null);
  assert.equal(two.readDraft('A.md').text, 'c');
  assert.equal(backend.data.get('unrelated'), 'x');
});

// -- Unsaved new entries (no path yet) ---------------------------------------

const newEntry = { text: 'From: [[Marsh]]\n\nReeds.', title: 'Reed', folder: 'Flora', updated: '2026-09-30T10:00:00.000Z' };

test('a new draft is kept under its own scoped key and read back with its id', () => {
  const backend = fakeBackend();
  const storage = createStorage({ backend });
  assert.equal(storage.writeNewDraft('d1', newEntry), true);
  assert.ok(backend.data.has(scopeKey('local', 'default', 'newdraft', 'd1')));
  assert.deepEqual(storage.readNewDraft('d1'), Object.assign({ v: 1, id: 'd1' }, newEntry));
  assert.equal(storage.readNewDraft('missing'), null);
});

test('new drafts are listed newest first and removed one at a time', () => {
  const storage = createStorage({ backend: fakeBackend() });
  storage.writeNewDraft('old', Object.assign({}, newEntry, { updated: '2026-09-29T10:00:00.000Z' }));
  storage.writeNewDraft('new', Object.assign({}, newEntry, { updated: '2026-09-30T12:00:00.000Z' }));
  assert.deepEqual(storage.listNewDrafts().map((item) => item.id), ['new', 'old']);
  storage.removeNewDraft('new');
  assert.deepEqual(storage.listNewDrafts().map((item) => item.id), ['old']);
});

test('the list skips what is not a readable draft, and other kinds with a similar name', () => {
  const backend = fakeBackend();
  const storage = createStorage({ backend });
  storage.writeNewDraft('ok', newEntry);
  backend.data.set(scopeKey('local', 'default', 'newdraft', 'bad'), '{not json');
  backend.data.set(scopeKey('local', 'default', 'newdraft', 'odd'), JSON.stringify({ v: 2, text: 'x' }));
  backend.data.set(scopeKey('local', 'default', 'draft', 'newdraft:x'), JSON.stringify(newEntry));
  assert.deepEqual(storage.listNewDrafts().map((item) => item.id), ['ok']);
});

test('new drafts never cross accounts or worlds, and clearAccount removes them', () => {
  const backend = fakeBackend();
  const one = createStorage({ backend, accountScope: 'u1', worldScope: 'w1' });
  const other = createStorage({ backend, accountScope: 'u2', worldScope: 'w1' });
  const sibling = createStorage({ backend, accountScope: 'u1', worldScope: 'w2' });
  one.writeNewDraft('d', newEntry);
  assert.deepEqual(other.listNewDrafts(), []);
  assert.deepEqual(sibling.listNewDrafts(), []);
  other.writeNewDraft('d', newEntry);
  one.clearAccount();
  assert.deepEqual(one.listNewDrafts(), []);
  assert.equal(other.listNewDrafts().length, 1);
});

test('new-draft access is guarded when storage throws', () => {
  const backend = fakeBackend();
  const storage = createStorage({ backend });
  storage.writeNewDraft('d', newEntry);
  backend.failAll = true;
  assert.equal(storage.readNewDraft('d'), null);
  assert.deepEqual(storage.listNewDrafts(), []);
  assert.equal(storage.writeNewDraft('d', newEntry), false);
  assert.doesNotThrow(() => storage.removeNewDraft('d'));
});

// -- Listing and clearing drafts (the welcome screen) ------------------------

test('listDrafts lists existing-entry drafts newest first, with legacy ones in the local scope', () => {
  const backend = fakeBackend({
    [LEGACY_PREFIX.draft + 'Old/Legacy.md']: JSON.stringify({ text: 'legacy', revision: 'r0', updated: '2026-09-01T00:00:00.000Z' }),
  });
  const storage = createStorage({ backend });
  storage.writeDraft('People/Ada.md', draft);
  storage.writeDraft('People/Bo.md', Object.assign({}, draft, { text: 'newer', updated: '2026-09-30T09:00:00.000Z' }));
  storage.writeRecovery('People/Ada.md', draft);
  const listed = storage.listDrafts();
  assert.deepEqual(listed.map((item) => item.path), ['People/Bo.md', 'People/Ada.md', 'Old/Legacy.md']);
  assert.equal(listed[0].text, 'newer');
});

test('listDrafts skips unreadable records, recoveries and other scopes', () => {
  const backend = fakeBackend();
  const mine = createStorage({ backend, accountScope: 'u1', worldScope: 'w1' });
  const other = createStorage({ backend, accountScope: 'u2', worldScope: 'w1' });
  mine.writeDraft('a.md', draft);
  other.writeDraft('b.md', draft);
  mine.writeRecovery('c.md', draft);
  backend.data.set(scopeKey('u1', 'w1', 'draft', 'bad.md'), '{not json');
  assert.deepEqual(mine.listDrafts().map((item) => item.path), ['a.md']);
  // Legacy drafts are only found in the default scope.
  backend.data.set(LEGACY_PREFIX.draft + 'old.md', JSON.stringify(draft));
  assert.deepEqual(mine.listDrafts().map((item) => item.path), ['a.md']);
});

test('clearDrafts removes drafts, new drafts and recovery copies and nothing else', () => {
  const backend = fakeBackend({
    [LEGACY_PREFIX.draft + 'Old/Legacy.md']: JSON.stringify(draft),
    [LEGACY_PREFIX.recovery + 'Old/Legacy.md']: JSON.stringify(draft),
  });
  const storage = createStorage({ backend });
  storage.writeDraft('People/Ada.md', draft);
  storage.writeRecovery('People/Ada.md', draft);
  storage.writeNewDraft('n1', newEntry);
  storage.writeNewDraft('n2', newEntry);
  storage.writePref('benchCollapsed', true);
  storage.writeRecent([{ path: 'a.md', title: 'A' }]);
  storage.writeKept(['moss']);
  storage.writeRecentFolders('v', ['People']);
  assert.deepEqual(storage.clearDrafts(), { drafts: 2, newDrafts: 2, recoveries: 2 });
  assert.deepEqual(storage.listDrafts(), []);
  assert.deepEqual(storage.listNewDrafts(), []);
  assert.equal(storage.readRecovery('People/Ada.md'), null);
  assert.equal(Array.from(backend.data.keys()).some((name) => name.indexOf('randomwords.world.') === 0), false);
  assert.equal(storage.readPref('benchCollapsed'), true);
  assert.equal(storage.readRecent().length, 1);
  assert.deepEqual(storage.readKept(), ['moss']);
  assert.deepEqual(storage.readRecentFolders('v'), ['People']);
});

test('clearDrafts leaves another account or world alone and survives blocked storage', () => {
  const backend = fakeBackend();
  const one = createStorage({ backend, accountScope: 'u1', worldScope: 'w1' });
  const other = createStorage({ backend, accountScope: 'u1', worldScope: 'w2' });
  one.writeDraft('a.md', draft);
  other.writeDraft('a.md', draft);
  one.clearDrafts();
  assert.equal(one.listDrafts().length, 0);
  assert.equal(other.listDrafts().length, 1);
  backend.failAll = true;
  assert.deepEqual(one.clearDrafts(), { drafts: 0, newDrafts: 0, recoveries: 0 });
  assert.deepEqual(one.listDrafts(), []);
});

test('recent entries round-trip, are capped at eight and ignore junk', () => {
  const backend = fakeBackend();
  const storage = createStorage({ backend });
  assert.deepEqual(storage.readRecent(), []);
  const items = Array.from({ length: 11 }, (_, i) => ({ path: 'n' + i + '.md', title: 'N' + i, opened: 't' }));
  assert.equal(storage.writeRecent(items), true);
  assert.deepEqual(storage.readRecent().map((item) => item.path), items.slice(0, 8).map((item) => item.path));
  backend.data.set(scopeKey('local', 'default', 'recent-entries', 'list'), JSON.stringify({ v: 1, items: [null, { title: 'x' }, { path: 'ok.md' }] }));
  assert.deepEqual(storage.readRecent().map((item) => item.path), ['ok.md']);
  backend.data.set(scopeKey('local', 'default', 'recent-entries', 'list'), '{nope');
  assert.deepEqual(storage.readRecent(), []);
  backend.failAll = true;
  assert.equal(storage.writeRecent(items), false);
  assert.deepEqual(storage.readRecent(), []);
});
