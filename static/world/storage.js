// The only module that touches localStorage.
//
// Keys are scoped by account and world so a hosted deployment never reads
// another account's drafts:  rw:v2:<account>:<world>:<kind>[:<id>]
//
// Before scoping, keys were global to the origin. In the default local scope
// (and only there) a missing new key falls back to its legacy key; the value
// is copied to the new key and the legacy key removed once the copy is
// confirmed, so an existing unsaved draft is never lost. Removing a value
// removes both keys, otherwise a stale legacy copy could resurface.

import { config, DEFAULT_CONFIG } from './config.js';

export const LEGACY_PREFIX = {
  draft: 'randomwords.world.draft.v1:',
  recovery: 'randomwords.world.recovery.v1:',
  recentFolders: 'randomwords.world.recent-folders.v1:',
};

// Also read by the word-bench page (app.js), which this scheme does not own.
export const LEGACY_KEPT_KEY = 'randomwords.kept.v1';

const MAX_RECENT_FOLDERS = 8;
const MAX_RECENT_ENTRIES = 8;

export function scopeKey(accountScope, worldScope, kind, id) {
  const prefix = 'rw:v2:' + encodeURIComponent(accountScope) + ':' + encodeURIComponent(worldScope) + ':';
  return prefix + kind + (id === undefined ? '' : ':' + id);
}

// Wraps window.localStorage lazily: even touching it can throw.
export function browserBackend() {
  return {
    getItem: (key) => globalThis.localStorage.getItem(key),
    setItem: (key, value) => globalThis.localStorage.setItem(key, value),
    removeItem: (key) => globalThis.localStorage.removeItem(key),
    keys: () => {
      const store = globalThis.localStorage;
      const names = [];
      for (let i = 0; i < store.length; i++) names.push(store.key(i));
      return names;
    },
  };
}

// `backend` needs getItem/setItem/removeItem/keys. Every access is guarded.
export function createStorage(options) {
  const backend = options.backend;
  const accountScope = options.accountScope || DEFAULT_CONFIG.accountScope;
  const worldScope = options.worldScope || DEFAULT_CONFIG.worldScope;
  const legacyAllowed = accountScope === DEFAULT_CONFIG.accountScope
    && worldScope === DEFAULT_CONFIG.worldScope;

  const get = (key) => { try { return backend.getItem(key); } catch (_) { return null; } };
  const remove = (key) => { try { backend.removeItem(key); } catch (_) { /* ignore */ } };
  const set = (key, value) => {
    try { backend.setItem(key, value); return true; } catch (_) { return false; }
  };
  const key = (kind, id) => scopeKey(accountScope, worldScope, kind, id);

  // Reads the raw string for `kind`, migrating a legacy value when present.
  function readRaw(kind, id, legacyKey) {
    const current = key(kind, id);
    const value = get(current);
    if (value != null) return value;
    if (!legacyAllowed || !legacyKey) return null;
    const old = get(legacyKey);
    if (old == null) return null;
    if (set(current, old) && get(current) === old) remove(legacyKey);
    return old;
  }

  function writeRaw(kind, id, legacyKey, value) {
    if (!set(key(kind, id), value)) return false;
    if (legacyAllowed && legacyKey) remove(legacyKey);
    return true;
  }

  function removeRaw(kind, id, legacyKey) {
    remove(key(kind, id));
    if (legacyAllowed && legacyKey) remove(legacyKey);
  }

  function parse(raw) {
    try { return JSON.parse(raw == null ? 'null' : raw); } catch (_) { return null; }
  }

  const legacyFor = (kind, id) => LEGACY_PREFIX[kind] + id;

  // Drafts and recoveries hold {text, revision, updated[, recoveredAt]}.
  function noteStore(kind) {
    return {
      read: (path) => parse(readRaw(kind, path, legacyFor(kind, path))),
      write: (path, value) => writeRaw(kind, path, legacyFor(kind, path), JSON.stringify(value)),
      remove: (path) => removeRaw(kind, path, legacyFor(kind, path)),
    };
  }
  const drafts = noteStore('draft');
  const recoveries = noteStore('recovery');

  // Unsaved new entries have no path to key them by, so each gets an id:
  // {v: 1, id, text, title, folder, ..., updated}. They live on this device
  // only; the welcome screen lists them and offers to clear them.
  const newDraftPrefix = () => key('newdraft') + ':';

  function readNewDraft(id) {
    const saved = parse(readRaw('newdraft', id, null));
    return saved && saved.v === 1 && typeof saved.text === 'string' ? saved : null;
  }

  function writeNewDraft(id, value) {
    return writeRaw('newdraft', id, null, JSON.stringify(Object.assign({}, value, { v: 1, id })));
  }

  function removeNewDraft(id) {
    removeRaw('newdraft', id, null);
  }

  // Newest first. Anything unreadable is skipped, never thrown on.
  function listNewDrafts() {
    let names = [];
    try { names = backend.keys(); } catch (_) { names = []; }
    return names
      .filter((name) => name.indexOf(newDraftPrefix()) === 0)
      .map((name) => readNewDraft(name.slice(newDraftPrefix().length)))
      .filter(Boolean)
      .sort((a, b) => String(b.updated || '').localeCompare(String(a.updated || '')));
  }

  // Names (after `prefix`) of every key that starts with it.
  function namesUnder(prefix) {
    let names = [];
    try { names = backend.keys(); } catch (_) { names = []; }
    return names.filter((name) => name.indexOf(prefix) === 0).map((name) => name.slice(prefix.length));
  }

  // Every unsaved edit to an existing entry on this device, newest first:
  // [{path, text, revision, updated}]. Local scope also finds drafts still
  // under their legacy keys, which are otherwise only migrated when read.
  function listDrafts() {
    return pathsOf('draft')
      .map((path) => {
        const saved = drafts.read(path);
        return saved && typeof saved.text === 'string' ? Object.assign({}, saved, { path }) : null;
      })
      .filter(Boolean)
      .sort((a, b) => String(b.updated || '').localeCompare(String(a.updated || '')));
  }

  // Paths with a stored copy of `kind` under its scoped key, or (local scope) its legacy key.
  function pathsOf(kind) {
    const paths = new Set(namesUnder(key(kind) + ':'));
    if (legacyAllowed) namesUnder(LEGACY_PREFIX[kind]).forEach((path) => paths.add(path));
    return Array.from(paths);
  }

  // "Clear drafts on this device": every unsaved draft, new or on an existing
  // entry, and the recovery copies. Returns how many of each were removed.
  function clearDrafts() {
    const draftPaths = pathsOf('draft');
    const recoveryPaths = pathsOf('recovery');
    const newIds = namesUnder(newDraftPrefix());
    draftPaths.forEach(drafts.remove);
    recoveryPaths.forEach(recoveries.remove);
    newIds.forEach(removeNewDraft);
    return { drafts: draftPaths.length, newDrafts: newIds.length, recoveries: recoveryPaths.length };
  }

  // The last entries opened here, newest first: [{path, title, opened}].
  function readRecent() {
    const saved = parse(readRaw('recent-entries', 'list', null));
    if (!saved || saved.v !== 1 || !Array.isArray(saved.items)) return [];
    return saved.items
      .filter((item) => item && typeof item.path === 'string' && item.path)
      .slice(0, MAX_RECENT_ENTRIES);
  }

  function writeRecent(items) {
    return writeRaw('recent-entries', 'list', null, JSON.stringify({ v: 1, items: items.slice(0, MAX_RECENT_ENTRIES) }));
  }

  // `vaultKey` identifies the vault on this origin (see create.js).
  function readRecentFolders(vaultKey) {
    const saved = parse(readRaw('recent-folders', vaultKey, legacyFor('recentFolders', vaultKey)));
    if (!saved || saved.v !== 1 || !Array.isArray(saved.folders)) return [];
    return saved.folders
      .filter((path) => typeof path === 'string' && path.length > 0)
      .slice(0, MAX_RECENT_FOLDERS);
  }

  function writeRecentFolders(vaultKey, folders) {
    const value = JSON.stringify({ v: 1, folders: folders.slice(0, MAX_RECENT_FOLDERS) });
    return writeRaw('recent-folders', vaultKey, legacyFor('recentFolders', vaultKey), value);
  }

  // Kept words are shared with the word-bench page, which only knows the
  // unscoped key, so the local scope keeps using it. Nothing is migrated.
  const keptKey = () => (legacyAllowed ? LEGACY_KEPT_KEY : key('kept'));

  function readKept() {
    const saved = parse(get(keptKey()));
    if (!saved || saved.v !== 1 || !Array.isArray(saved.words)) return [];
    return saved.words.filter((word) => typeof word === 'string');
  }

  function writeKept(words) {
    return set(keptKey(), JSON.stringify({ v: 1, words }));
  }

  // Small per-world interface choices (a collapsed panel, say): a JSON value or null.
  function readPref(name) {
    return parse(readRaw('pref', name));
  }

  function writePref(name, value) {
    return writeRaw('pref', name, null, JSON.stringify(value));
  }

  // For logout: forget everything stored under this account, in any world.
  function clearAccount() {
    const prefix = 'rw:v2:' + encodeURIComponent(accountScope) + ':';
    let names = [];
    try { names = backend.keys(); } catch (_) { names = []; }
    names.filter((name) => name.indexOf(prefix) === 0).forEach(remove);
  }

  return {
    accountScope,
    worldScope,
    readDraft: drafts.read,
    writeDraft: drafts.write,
    removeDraft: drafts.remove,
    readRecovery: recoveries.read,
    writeRecovery: recoveries.write,
    removeRecovery: recoveries.remove,
    readNewDraft,
    writeNewDraft,
    removeNewDraft,
    listNewDrafts,
    listDrafts,
    clearDrafts,
    readRecent,
    writeRecent,
    readRecentFolders,
    writeRecentFolders,
    readKept,
    writeKept,
    readPref,
    writePref,
    clearAccount,
  };
}

export const storage = createStorage({
  backend: browserBackend(),
  accountScope: config.accountScope,
  worldScope: config.worldScope,
});
