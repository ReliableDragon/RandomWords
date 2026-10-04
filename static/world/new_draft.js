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

// What the text looked like when the draft opened (the prefilled headers).
// Leaving it as it was does not count as writing anything.
let initialText = '';

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
  storage.writePref(ACTIVE_PREF, draft.id);
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
    updated: new Date().toISOString(),
  };
}

// Keeps the draft when it holds something, forgets it when it does not.
// Returns false only when the browser refused the write.
export function persistNewDraft(text) {
  const draft = state.newDraft;
  if (!draft) return true;
  if (!draftHasContent(text, draft.title, initialText)) {
    storage.removeNewDraft(draft.id);
    return true;
  }
  return storage.writeNewDraft(draft.id, record(text)) !== false;
}

// The draft's saved record as an options object for makeDraft, plus its text.
export function draftFromRecord(saved) {
  return { draft: makeDraft(saved), text: saved.text };
}

// Stops tracking the open draft (it was saved, discarded or left behind).
export function closeNewDraft(options) {
  const draft = state.newDraft;
  if (!draft) return;
  if (options && options.forget) storage.removeNewDraft(draft.id);
  if (storage.readPref(ACTIVE_PREF) === draft.id) storage.writePref(ACTIVE_PREF, null);
  state.newDraft = null;
  initialText = '';
}

// Removes a draft's saved copy, wherever the editor has moved on to.
export function forgetNewDraft(id) {
  storage.removeNewDraft(id);
  if (storage.readPref(ACTIVE_PREF) === id) storage.writePref(ACTIVE_PREF, null);
}

// The draft the writer was in when the page last closed, if it was kept.
export function activeDraftId() {
  const id = storage.readPref(ACTIVE_PREF);
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
}
