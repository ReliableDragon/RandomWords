// The unsaved new entry: its shared state, and keeping it on this device.
//
// A new draft has no path yet, so `state.current` stays null and
// `state.newDraft` holds its title and placement; the text itself lives in
// the textarea. Unsaved drafts are kept in this browser (storage.js) so a
// reload or a closed tab never loses them.

import { state } from './state.js';
import { storage } from './storage.js';
import { draftHasContent, newDraftId } from './draft_text.js';

// The draft shown last, so a reload can pick it up again.
const ACTIVE_PREF = 'activeNewDraft';

// A fresh identity for this live document. It deliberately does not live in
// sessionStorage: browsers copy sessionStorage into duplicated/window.open
// tabs, which would let those tabs overwrite one another again.
let documentWriter = '';

function freshId(prefix) {
  try {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
      return prefix + globalThis.crypto.randomUUID();
    }
  } catch (_) { /* use the dependency-free fallback */ }
  return prefix + newDraftId(Date.now(), Math.random()) + '-' + newDraftId(Date.now(), Math.random());
}

function writerId() {
  if (!documentWriter) documentWriter = freshId('w-');
  return documentWriter;
}

function activeId(value) {
  if (typeof value === 'string') return value;
  return value && Object.prototype.hasOwnProperty.call(value, 'id') ? value.id : undefined;
}

function setActiveDraft(id) {
  const previous = storage.readSessionPref(ACTIVE_PREF);
  const marker = { id, replaces: activeId(previous) };
  // `replaces` lets this same session recognize a fallback after a transient
  // sessionStorage write failure without trusting an unrelated tab's pointer.
  if (storage.writeSessionPref(ACTIVE_PREF, marker) === false) storage.writePref(ACTIVE_PREF, marker);
}

function clearActiveDraft(id) {
  const active = storage.readSessionPref(ACTIVE_PREF);
  const fallback = storage.readPref(ACTIVE_PREF);
  if (activeId(active) === id || activeId(fallback) === id) {
    const marker = { id: null, replaces: id };
    const sessionKept = storage.writeSessionPref(ACTIVE_PREF, marker);
    if (sessionKept === false) storage.writePref(ACTIVE_PREF, marker);
    else if (fallback === id) storage.writePref(ACTIVE_PREF, null);
  }
}

// What the text looked like when the draft opened (the prefilled headers).
// Leaving it as it was does not count as writing anything.
let initialText = '';

const CONTENT_FIELDS = [
  'text', 'title', 'folder', 'folderSource', 'kind', 'template', 'insertedTemplate',
  'fromTargets', 'idea', 'again', 'copiedFrom',
];
const METADATA_FIELDS = CONTENT_FIELDS.filter((name) => name !== 'text');

function sameFields(left, right, fields) {
  return fields.every((name) => JSON.stringify(left && left[name]) === JSON.stringify(right && right[name]));
}

// Saving a new entry can migrate later text into the resulting existing-entry
// draft. The new-entry copy is then redundant only when all its other details
// still match the snapshot that was posted.
export function sameDraftMetadata(left, right) {
  return sameFields(left, right, METADATA_FIELDS);
}

export function makeDraft(options) {
  const given = options || {};
  return {
    id: given.id || newDraftId(Date.now(), Math.random()),
    title: given.title || '',
    folder: given.folder == null ? null : given.folder,
    // 'prefill' and 'chosen' folders are the writer's; only 'proposed' ones
    // are replaced when another place is picked.
    folderSource: given.folderSource || (given.folder == null ? '' : 'prefill'),
    kind: given.kind || '',
    template: given.template || '',
    // The template text this draft inserted, so a different template can
    // replace it while the writer has not written anything of their own.
    insertedTemplate: given.insertedTemplate || '',
    fromTargets: given.fromTargets || [],
    idea: given.idea || null,
    again: Boolean(given.again),
    copiedFrom: given.copiedFrom || '',
  };
}

// Makes `draft` the open entry (there is no path). `initial` is the text it
// was opened with.
export function startNewDraft(draft, initial) {
  initialText = initial || '';
  state.newDraft = draft;
  state.current = null;
  state.revision = null;
  state.savedText = initialText;
  state.lineEnding = '\n';
  state.dirty = false;
  state.conflict = null;
  state.nearby = null;
  setActiveDraft(draft.id);
}

// True when the draft holds words or a title the writer added.
export function draftHasChanges(text) {
  return Boolean(state.newDraft) && draftHasContent(text, state.newDraft.title, initialText);
}

function record(text) {
  const draft = state.newDraft;
  return {
    text,
    title: draft.title,
    folder: draft.folder,
    folderSource: draft.folderSource,
    kind: draft.kind,
    template: draft.template,
    insertedTemplate: draft.insertedTemplate,
    fromTargets: draft.fromTargets,
    idea: draft.idea,
    again: draft.again,
    copiedFrom: draft.copiedFrom,
    writer: writerId(),
    writeId: freshId('r-'),
    updated: new Date().toISOString(),
  };
}

// Keeps the draft when it holds something, forgets it when it does not.
// Returns false only when the browser refused the write.
export function persistNewDraft(text) {
  const draft = state.newDraft;
  if (!draft) return true;
  const ownership = storage.inspectNewDraft(draft.id);
  if (ownership.status === 'unreadable') return false;
  let copied = false;
  if (ownership.status === 'found' && ownership.value.writer !== writerId()) {
    const sourceId = draft.id;
    draft.id = freshId('d-copy-');
    draft.copiedFrom = sourceId;
    setActiveDraft(draft.id);
    copied = true;
  }
  if (!draftHasContent(text, draft.title, initialText)) {
    // Never delete a key which belongs to another document writer. A freshly
    // copied empty state has no record to remove.
    const current = storage.inspectNewDraft(draft.id);
    if (current.status === 'unreadable') return false;
    if (current.status === 'found' && current.value.writer === writerId()
      && storage.removeNewDraft(draft.id) === false) return false;
    return true;
  }
  const next = record(text);
  // Keep the persisted identity stable when nothing meaningful changed. Save
  // completion uses this identity to remove exactly the snapshot it posted.
  // Legacy records without a write identity must first be upgraded.
  if (!copied && ownership.status === 'found' && ownership.value.writer === writerId()
    && typeof ownership.value.writeId === 'string' && ownership.value.writeId
    && sameFields(ownership.value, next, CONTENT_FIELDS)) return true;
  if (storage.writeNewDraft(draft.id, next) === false) return false;
  return copied ? 'copied' : true;
}

// The draft's saved record as an options object for makeDraft, plus its text.
export function draftFromRecord(saved) {
  const mine = writerId();
  if (saved.writer === mine) return { draft: makeDraft(saved), text: saved.text, copied: false, kept: true };

  // A record without an owner is legacy data. Clone it too: two tabs can read
  // the same legacy record before either writes, so letting either claim its
  // shared key would preserve the original overwrite race.
  const id = freshId('d-copy-');
  const copy = Object.assign({}, saved, {
    id,
    writer: mine,
    writeId: freshId('r-'),
    copiedFrom: saved.id,
    updated: new Date().toISOString(),
  });
  const kept = storage.writeNewDraft(id, copy) !== false;
  return { draft: makeDraft(copy), text: saved.text, copied: true, kept };
}

// Stops tracking the open draft (it was saved, discarded or left behind).
export function closeNewDraft(options) {
  const draft = state.newDraft;
  if (!draft) return true;
  if (options && options.forget && !removeOwnedDraft(draft.id)) return false;
  clearActiveDraft(draft.id);
  state.newDraft = null;
  initialText = '';
  return true;
}

// Removes a draft's saved copy, wherever the editor has moved on to.
export function forgetNewDraft(id, expectedWriteId) {
  const removed = removeOwnedDraft(id, expectedWriteId);
  if (removed) clearActiveDraft(id);
  return removed;
}

function removeOwnedDraft(id, expectedWriteId) {
  const found = storage.inspectNewDraft(id);
  if (found.status === 'missing') return true;
  if (found.status !== 'found') return false;
  if (found.value.writer !== writerId()) return expectedWriteId === undefined;
  if (expectedWriteId !== undefined && found.value.writeId !== expectedWriteId) return false;
  return storage.removeNewDraft(id) !== false;
}

// The draft the writer was in when the page last closed, if it was kept.
export function activeDraftId() {
  const active = storage.readSessionPref(ACTIVE_PREF);
  const fallback = storage.readPref(ACTIVE_PREF);
  let id = activeId(active);
  if (fallback && typeof fallback === 'object' && Object.prototype.hasOwnProperty.call(fallback, 'id')) {
    if (id === undefined || fallback.replaces === id) id = fallback.id;
  }
  if (id === undefined) id = activeId(fallback);
  return typeof id === 'string' && storage.readNewDraft(id) ? id : null;
}

// Editor.saveEntry hands a new draft's save to whoever registers here (the
// create module), because saving also needs the folder tree and the
// placement panel, which the editor does not import.
let saver = null;

export function setDraftSaver(fn) {
  saver = typeof fn === 'function' ? fn : null;
}

export function requestDraftSave() {
  return saver ? saver() : Promise.resolve(false);
}

export function resetForTests() {
  initialText = '';
  saver = null;
  documentWriter = '';
}
