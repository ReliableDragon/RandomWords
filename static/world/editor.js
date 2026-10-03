// The entry editor: opening, editing, saving, conflicts and recovery.
//
// Other modules reach the textarea through the exports below (getText,
// insertAtCursor, replaceRange, stageReplacement) so drafts stay in sync.

import { world } from './api.js';
import { config } from './config.js';
import { clearEntryLinks, noteGeneration, setEntryLinks } from './draft_marks.js';
import { $, button, setStatus } from './dom.js';
import { renderBacklinks, renderEntryDiagnostics, renderMetadataSummary } from './entry_panels.js';
import { insertHeader } from './entry_header.js';
import { adjustCaret, diffSpan } from './draft_text.js';
import { emit, Events, on } from './events.js';
import { setWorldView, showPane } from './nav.js';
import {
  closeNewDraft, draftFromRecord, draftHasChanges, forgetNewDraft, persistNewDraft, requestDraftSave, startNewDraft,
} from './new_draft.js';
import { previewLabel, proportionalScroll, skippedText, splitFits } from './preview_layout.js';
import { revealRange } from './reveal.js';
import { replaceSpan, spanIsCurrent } from './spans.js';
import { state } from './state.js';
import { storage } from './storage.js';
import {
  detectLineEnding, draftBase, entryLinkTarget, entryTitle, textareaText, toDiskText,
} from './text.js';

const POLL_MS = 12000;
let pollTimer = null;
// The on-disk revision whose conflict the writer chose to ignore ("Keep draft").
let keptRevision = null;
// The latest openEntry call; a slower, earlier one must not replace it.
let openSequence = 0;
let saving = false;
let draftWarned = false;

const textarea = () => $('entryText');

// -- Text surface ----------------------------------------------------------

export function getText() {
  return textarea().value;
}

// Marks the draft changed and lets Nearby and others react.
function markEdited() {
  setDirty();
  emit(Events.DRAFT_CHANGED);
}

// Replaces the whole text with a version that differs only by a small edit
// (a From: line, template headings), keeping the writer's caret where it was
// in their own words. Does not steal focus.
export function applyTextChange(newText) {
  const field = textarea();
  const before = field.value;
  if (newText === before) return;
  const { start, end, replacement } = diffSpan(before, newText);
  const caret = adjustCaret(field.selectionStart, start, end, replacement.length);
  field.value = newText;
  field.setSelectionRange(caret, caret);
  markEdited();
}

// Replaces text[start, end) and puts the caret after the replacement, or
// selects the replacement with {select: true}.
export function replaceRange(start, end, replacement, options) {
  const field = textarea();
  field.value = replaceSpan(field.value, start, end, replacement);
  focusQuietly(field);
  const selectFrom = options && options.select ? start : start + replacement.length;
  field.setSelectionRange(selectFrom, start + replacement.length);
  markEdited();
}

// Focuses without letting the browser jump to the old caret position;
// revealSelection scrolls to the new one.
function focusQuietly(field) {
  field.focus({ preventScroll: true });
}

// Scrolls the page so the start of the selection is on screen.
export function revealSelection() {
  const field = textarea();
  revealRange(field, field.selectionStart);
}

export function insertAtCursor(value) {
  const field = textarea();
  replaceRange(field.selectionStart, field.selectionEnd, value);
}

// Stages a replacement of a span a report or suggestion described: opens the
// entry if needed, refuses when the text or revision has moved on, and
// otherwise applies the change unsaved with the new text selected.
// span: {path, revision, start, end, expected}. Resolves to true if staged.
export async function stageReplacement(span, replacement, messages) {
  const words = Object.assign({
    stale: 'That occurrence changed. Refresh and try again.',
    staged: 'Replacement staged. Review the highlighted text, then save.',
  }, messages);
  if (state.current !== span.path) {
    await openEntry(span.path);
  } else {
    setWorldView('desk');
    showPane('entry');
  }
  if (state.current !== span.path) return false;
  if (!spanIsCurrent({ revision: state.revision, text: getText() }, span)) {
    showNotice(words.stale, true);
    return false;
  }
  replaceRange(span.start, span.end, replacement, { select: true });
  showNotice(words.staged);
  // The notice sits above the text, so scroll once it has taken its room.
  revealSelection();
  return true;
}

// -- Notices ---------------------------------------------------------------

export function showNotice(text, isError) {
  const notice = $('saveNotice');
  notice.textContent = text;
  notice.className = 'save-notice' + (isError ? ' error' : '');
  notice.hidden = false;
}

// Adds a button to the current notice (used to offer a retry).
export function addNoticeAction(node) {
  $('saveNotice').appendChild(node);
}

// -- Draft state and recovery ----------------------------------------------

// Once per failing stretch: typing must not bury the notice under repeats.
function warnDraftNotKept() {
  if (draftWarned) return;
  draftWarned = true;
  showNotice('This browser could not keep a copy of your draft (its storage is full or blocked). '
    + 'Save soon so nothing is lost.', true);
}

function storeDraft() {
  if (state.newDraft) {
    const kept = persistNewDraft(getText());
    if (kept === false) warnDraftNotKept();
    else {
      draftWarned = false;
      if (kept === 'copied') {
        showNotice('Kept this tab\'s changes as a separate draft because the earlier browser draft changed elsewhere. '
          + 'Both versions remain available on this device.', true);
      }
    }
    return;
  }
  if (!state.current) return;
  if (state.dirty) {
    const kept = storage.writeDraft(state.current, {
      text: getText(), revision: state.revision, updated: new Date().toISOString(),
    });
    if (kept === false) warnDraftNotKept();
    else draftWarned = false;
  } else {
    storage.removeDraft(state.current);
  }
}

export function setDirty() {
  const isNew = Boolean(state.newDraft);
  state.dirty = isNew ? draftHasChanges(getText()) : getText() !== state.savedText;
  const label = $('draftState');
  if (isNew) label.textContent = state.dirty ? 'Unsaved draft, kept on this device' : 'New entry, not saved yet';
  else label.textContent = state.dirty ? 'Unsaved draft' : 'Saved';
  label.className = 'draft-state' + (state.dirty ? ' is-dirty' : '');
  storeDraft();
}

function stashRecovery(path, draft) {
  if (!path || !draft) return;
  storage.writeRecovery(path, Object.assign({}, draft, { recoveredAt: new Date().toISOString() }));
}

function showRecovery(path) {
  const notice = $('recoveryNotice');
  if (!storage.readRecovery(path) || !notice) return;
  notice.dataset.path = path;
  $('recoveryText').textContent = 'A previous draft for this entry is kept in browser recovery.';
  notice.hidden = false;
}

function restoreRecovery(path, draft) {
  if (!draft || path !== state.current) return;
  textarea().value = draft.text || '';
  markEdited();
  $('recoveryNotice').hidden = true;
  showNotice('Recovered the earlier draft. Review and save when ready.');
}

async function reopenRecovery() {
  const path = $('recoveryNotice').dataset.path;
  const draft = storage.readRecovery(path);
  if (!draft) return;
  if (path !== state.current) await openEntry(path);
  restoreRecovery(path, draft);
}

function dismissRecovery() {
  const path = $('recoveryNotice').dataset.path;
  if (path) storage.removeRecovery(path);
  $('recoveryNotice').hidden = true;
}

// -- Conflicts -------------------------------------------------------------

function openConflict(diskText, diskRevision) {
  state.conflict = {
    text: getText(),
    currentText: textareaText(diskText || ''),
    currentRevision: diskRevision,
    lineEnding: detectLineEnding(diskText),
  };
  $('conflictDraft').textContent = state.conflict.text;
  $('conflictDisk').textContent = state.conflict.currentText;
  $('conflictPanel').hidden = false;
}

function closeConflict() {
  state.conflict = null;
  keptRevision = null;
  $('conflictPanel').hidden = true;
}

function keepDraft() {
  keptRevision = state.conflict ? state.conflict.currentRevision : null;
  storeDraft();
  $('conflictPanel').hidden = true;
  showNotice('Draft kept in browser recovery.');
}

function reloadDiskVersion() {
  const conflict = state.conflict;
  if (!conflict) return;
  stashRecovery(state.current, { text: conflict.text, revision: state.revision, updated: new Date().toISOString() });
  state.revision = conflict.currentRevision;
  state.lineEnding = conflict.lineEnding || '\n';
  state.savedText = conflict.currentText;
  textarea().value = state.savedText;
  state.dirty = false;
  closeConflict();
  setDirty();
  showRecovery(state.current);
  emit(Events.DRAFT_CHANGED);
  showNotice('Reloaded disk version. The previous draft is available from the recovery notice.');
}

function replaceReviewedVersion() {
  if (!state.conflict) return;
  state.lineEnding = state.conflict.lineEnding || state.lineEnding;
  saveEntry(state.conflict.currentRevision);
}

// -- Saving ----------------------------------------------------------------

export async function saveEntry(replaceRevision) {
  if (state.newDraft) return requestDraftSave();
  if (!state.current || saving) return;
  keptRevision = null;
  const payload = { path: state.current, text: toDiskText(getText(), state.lineEnding), revision: state.revision };
  if (replaceRevision) payload.replace_revision = replaceRevision;
  saving = true;
  try {
    const data = await world.post('/entry', payload);
    if (state.current !== payload.path) {
      // The writer opened another entry while this saved; leave that one alone.
      emit(Events.VAULT_CHANGED, { generation: data.generation, path: payload.path });
      showNotice('Saved ' + payload.path + '.');
      return;
    }
    state.revision = data.revision;
    state.savedText = textareaText(payload.text);
    state.dirty = false;
    closeConflict();
    setDirty();
    // The server names where replaced bytes went; the UI never assumes.
    const recovery = data.recovery_path || data.recovery;
    showNotice(recovery ? 'Saved. Replaced bytes were preserved at ' + recovery : 'Saved.');
    emit(Events.DRAFT_CHANGED);
    emit(Events.VAULT_CHANGED, { generation: data.generation, path: payload.path });
    watchRevision();
    refreshEntryData();
  } catch (error) {
    if (state.current !== payload.path) return;
    if (error.status !== 409) {
      showNotice(error.message, true);
      return;
    }
    openConflict(error.data.text, error.data.revision);
    setDirty();
    storeDraft();
  } finally {
    saving = false;
  }
}

// Checks the open entry every few seconds for edits made outside the desk.
function watchRevision() {
  clearInterval(pollTimer);
  if (!state.current) return;
  const watched = state.current;
  pollTimer = setInterval(() => checkRevision(watched), POLL_MS);
}

async function checkRevision(watched) {
  if (state.current !== watched || saving) return;
  const began = state.revision;
  try {
    const data = await world.get('/entry', { path: watched });
    // A save, reload or another entry may have landed while this was in
    // flight; what it saw is then out of date and must not be applied.
    if (state.current !== watched || state.revision !== began || saving) return;
    if (data.revision === state.revision) return;
    if (state.dirty) {
      // Raise the panel once per disk revision, not on every poll.
      const showing = state.conflict && state.conflict.currentRevision === data.revision;
      if (data.revision === keptRevision || showing) return;
      openConflict(data.text, data.revision);
      showNotice('Disk version changed while you were editing.', true);
      return;
    }
    state.lineEnding = detectLineEnding(data.text);
    state.revision = data.revision;
    state.savedText = textareaText(data.text);
    textarea().value = state.savedText;
    renderPreview(data.html, data.skipped);
    renderBacklinks(data.backlinks || [], openEntry);
    renderWords(data.entry);
    setEntryLinks(data.links, data.generation, data.entry);
    setDirty();
    emit(Events.ENTRY_REFRESHED, { path: watched, entry: data.entry || null, links: data.links || [] });
    emit(Events.DRAFT_CHANGED);
  } catch (_) {
    // A failed poll is not worth interrupting the writer for.
  }
}

// -- Opening ---------------------------------------------------------------

export function renderPreview(html, skipped) {
  if (typeof html !== 'string') return;
  const preview = $('entryPreview');
  preview.innerHTML = html;
  preview.querySelectorAll('a').forEach(bindPreviewLink);
  const note = skippedText(skipped);
  $('previewSkipped').textContent = note;
  $('previewSkipped').hidden = !note;
  syncPreviewScroll();
}

// Re-reads the open entry for what only the server knows: link statuses,
// backlinks and the word count. Called after saves and when Nearby sees the
// vault move on. A call made while one is running schedules one more.
let refreshing = false;
let refreshAgain = false;

export async function refreshEntryData() {
  const path = state.current;
  if (!path) return;
  if (refreshing) {
    refreshAgain = true;
    return;
  }
  refreshing = true;
  try {
    const data = await world.get('/entry', { path });
    if (state.current === path) {
      setEntryLinks(data.links, data.generation, data.entry);
      renderBacklinks(data.backlinks || [], openEntry);
      // The word count describes the saved text, so only trust a copy of it.
      if (data.revision === state.revision) {
        renderWords(data.entry);
        emit(Events.ENTRY_REFRESHED, { path, entry: data.entry || null, links: data.links || [] });
      }
    }
    noteGeneration(data.generation);
  } catch (_) {
    // These are extras; the entry itself is already on screen.
  } finally {
    refreshing = false;
    if (refreshAgain) {
      refreshAgain = false;
      refreshEntryData();
    }
  }
}

function bindPreviewLink(anchor) {
  const href = anchor.getAttribute('href') || '';
  const target = entryLinkTarget(href, config.worldApiBase, location.href);
  if (!target) return;
  anchor.addEventListener('click', (event) => {
    event.preventDefault();
    if (!target.path) return;
    if (event.ctrlKey || event.metaKey) emit(Events.REFERENCE_REQUESTED, { path: target.path });
    else openEntry(target.path);
  });
}

// Scenes carry their own diagnostics; older responses need the story report.
async function loadEntryDiagnostics(path, diagnostics) {
  if (Array.isArray(diagnostics)) {
    renderEntryDiagnostics(diagnostics);
    return;
  }
  renderEntryDiagnostics([]);
  try {
    const story = await world.get('/story');
    if (state.current !== path) return;
    const scene = (story.scenes || []).find((item) => item.path === path);
    renderEntryDiagnostics(scene && scene.diagnostics);
  } catch (_) {
    // Diagnostics are a bonus; the entry is already open.
  }
}

function confirmLeaveDirty(path) {
  if (!state.current || !state.dirty || state.current === path) return true;
  if (!window.confirm('Keep this unsaved draft in browser recovery and open another entry?')) return false;
  storeDraft();
  return true;
}

function resetForOpen() {
  clearInterval(pollTimer);
  emit(Events.ENTRY_OPENING);
  clearEntryLinks();
  closeConflict();
  $('saveNotice').hidden = true;
}

// Loads the text, restoring an unsaved browser draft when one differs.
function loadText(data, requestedPath) {
  state.current = data.path || requestedPath;
  state.revision = data.revision;
  state.lineEnding = detectLineEnding(data.text);
  state.savedText = textareaText(data.text);
  state.dirty = false;
  const recovered = storage.readDraft(state.current);
  if (recovered && recovered.text !== state.savedText) {
    textarea().value = textareaText(recovered.text);
    state.dirty = true;
    const base = draftBase(recovered, data.revision);
    if (base.stale) {
      // Keep the draft's own base so Save meets the normal conflict review
      // instead of overwriting whatever changed on disk since.
      state.revision = base.revision;
      showNotice('Recovered a draft written before this note last changed on disk. '
        + 'Saving will ask you to review both versions.', true);
    } else {
      showNotice('Recovered an unsaved browser draft for this entry.');
    }
  } else {
    textarea().value = state.savedText;
  }
}

function renderHeading(data) {
  const entry = data.entry;
  $('entryTitle').textContent = (entry && entry.title) || entryTitle({ path: state.current });
  $('entryFolder').textContent = state.current.includes('/')
    ? state.current.slice(0, state.current.lastIndexOf('/'))
    : 'Vault root';
  renderWords(entry);
}

function renderWords(entry) {
  $('entryWords').textContent = entry && entry.words != null ? entry.words + ' words' : '';
}

function highlightSpan(highlight) {
  const field = textarea();
  if (!highlight || highlight.start > highlight.end || highlight.end > field.value.length) return;
  focusQuietly(field);
  field.setSelectionRange(highlight.start, highlight.end);
  revealSelection();
}

// options.highlight: {start, end} UTF-16 offsets to select once open.
// Resolves to true when the entry is open (false if cancelled or failed).
export async function openEntry(path, options) {
  if (!confirmLeaveDirty(path)) return false;
  const mine = ++openSequence;
  resetForOpen();
  try {
    const data = await world.get('/entry', { path });
    if (mine !== openSequence) return false; // a later open won
    const leftDraft = leaveNewDraft();
    if (leftDraft === false) return false;
    loadText(data, path);
    renderHeading(data);
    renderMetadataSummary(data.entry);
    loadEntryDiagnostics(state.current, data.diagnostics || (data.entry && data.entry.diagnostics));
    setWorldView('desk');
    showPane('entry');
    renderBacklinks(data.backlinks || [], openEntry);
    renderPreview(data.html, data.skipped);
    setEntryLinks(data.links, data.generation, data.entry);
    noteGeneration(data.generation, true);
    showRecovery(state.current);
    setDirty();
    watchRevision();
    highlightSpan(options && options.highlight);
    if (leftDraft && $('saveNotice').hidden) offerBackToDraft(leftDraft);
    emit(Events.ENTRY_OPENED, {
      path: state.current, title: $('entryTitle').textContent, entry: data.entry || null, links: data.links || [],
    });
    emit(Events.DRAFT_CHANGED);
    return true;
  } catch (error) {
    if (mine === openSequence) {
      setStatus(error.message, 'error');
      if (state.current || state.newDraft) emit(Events.DRAFT_CHANGED); // the old entry or draft is still showing
    }
    return false;
  }
}

// -- New drafts ------------------------------------------------------------
//
// An unsaved new entry has no path. While one is open the pane wears
// `is-new-draft`: the stylesheet swaps the title field and placement bar in,
// and the backlinks and other saved-entry extras out. Its text is in the
// textarea like any entry's, so Nearby, autocomplete and drift marks work.

// Shows the draft in state.newDraft (see new_draft.js startNewDraft) with
// `text`, the caret at the end, ready to write.
export function showNewDraft(text) {
  const draft = state.newDraft;
  if (!draft) return;
  openSequence++; // an entry still loading must not replace the draft
  clearInterval(pollTimer);
  emit(Events.ENTRY_OPENING);
  clearEntryLinks();
  closeConflict();
  $('saveNotice').hidden = true;
  $('recoveryNotice').hidden = true;
  renderEntryDiagnostics([]);
  renderMetadataSummary(null);
  $('entryFolder').textContent = 'A new entry';
  $('entryWords').textContent = '';
  $('draftTitle').value = draft.title;
  $('entryPane').classList.add('is-new-draft');
  const field = textarea();
  field.value = text;
  setWorldView('desk');
  showPane('entry');
  setDirty();
  noteGeneration(undefined, true);
  focusQuietly(field);
  field.setSelectionRange(text.length, text.length);
  emit(Events.CREATE_OPENED, { id: draft.id });
  emit(Events.DRAFT_CHANGED);
}

// Reopens a draft kept on this device. False when it is gone.
export function resumeNewDraft(id) {
  if (!storage.readNewDraft(id)) return false;
  const wasCurrent = Boolean(state.newDraft && state.newDraft.id === id);
  const left = leaveNewDraft();
  if (left === false) return false;
  // Leaving can persist the currently open target again (or fork it after an
  // ownership change), so never reopen the stale snapshot read above.
  const resumeId = wasCurrent && left ? left.id : id;
  const saved = storage.readNewDraft(resumeId);
  if (!saved) return false;
  const { draft, text, copied, kept } = draftFromRecord(saved);
  startNewDraft(draft, '');
  showNewDraft(text);
  if (copied && kept) {
    showNotice('Opened a separate copy to preserve the earlier browser draft safely. '
      + 'Both versions are kept on this device.', true);
  } else if (copied) {
    draftWarned = true;
    showNotice('Opened a separate copy to preserve the earlier browser draft safely. '
      + 'The earlier copy is still kept, but this browser could not keep this tab\'s copy. Save soon.', true);
  }
  return true;
}

// Stops showing the open draft because something else is opening. The draft
// stays in browser storage when it holds anything; returns {id, title} then.
export function leaveNewDraft() {
  const draft = state.newDraft;
  if (!draft) return null;
  const changed = draftHasChanges(getText());
  // Even an empty state must be persisted: it can represent deletion of a
  // previously kept draft, and leaving is unsafe until that deletion lands.
  const result = persistNewDraft(getText());
  if (result === false) {
    warnDraftNotKept();
    return false;
  }
  if (result === 'copied') {
    showNotice('Kept this tab\'s changes as a separate draft because the earlier browser draft changed elsewhere. '
      + 'Both versions remain available on this device.', true);
  }
  const kept = changed ? { id: draft.id, title: draft.title.trim() } : null;
  closeNewDraft();
  $('entryPane').classList.remove('is-new-draft');
  return kept;
}

function offerBackToDraft(kept) {
  showNotice('Your new entry' + (kept.title ? ' "' + kept.title + '"' : '')
    + ' is not saved yet. It is kept on this device.');
  addNoticeAction(button('Back to the draft', 'btn btn-small btn-quiet', () => resumeNewDraft(kept.id)));
}

// Throws the open draft away (the caller has already confirmed).
export function discardNewDraft() {
  if (!state.newDraft) return;
  if (closeNewDraft({ forget: true }) === false) {
    showNotice('This browser could not remove its kept copy of the draft. The draft is still open; try again.', true);
    return;
  }
  emit(Events.ENTRY_OPENING);
  $('entryPane').classList.remove('is-new-draft');
  textarea().value = '';
  state.dirty = false;
  state.savedText = '';
  showPane('welcome');
}

// The draft was saved as `saved.path`: it becomes that entry where it stands,
// text and caret untouched. saved: {path, revision, title, text}, where text
// is what was written (anything typed since keeps the entry unsaved).
export async function adoptSavedDraft(saved) {
  if (!state.newDraft) return false;
  const draftId = saved.draftId || state.newDraft.id;
  const currentDraftId = state.newDraft.id;
  // /new ends a nonempty file with a newline; mirror it so the editor's idea
  // of the saved text matches the disk and the next save does not drop it.
  const posted = textareaText(saved.text);
  const text = posted && !posted.endsWith('\n') ? posted + '\n' : posted;
  const field = textarea();
  if (field.value === posted && text !== posted) {
    const { selectionStart, selectionEnd } = field;
    field.value = text;
    field.setSelectionRange(selectionStart, selectionEnd);
  }
  closeNewDraft();
  state.current = saved.path;
  state.revision = saved.revision;
  state.lineEnding = '\n';
  state.savedText = text;
  state.dirty = false;
  $('entryPane').classList.remove('is-new-draft');
  renderHeading({ entry: { title: saved.title } });
  setDirty();
  const removedPosted = saved.writeId !== undefined && forgetNewDraft(draftId, saved.writeId);
  const retainedId = currentDraftId !== draftId ? currentDraftId : draftId;
  const retainedDraft = storage.inspectNewDraft(retainedId);
  let storageNote = '';
  if (state.dirty) {
    const migrated = storage.readDraft(saved.path);
    const migratedOkay = migrated && migrated.text === field.value && migrated.revision === state.revision;
    if (retainedDraft.status === 'found') {
      storageNote = ' A separate browser draft with later changes also remains kept on this device.';
    } else if (!migratedOkay) {
      storageNote = ' Later changes are still open here, but browser storage could not keep or verify them. Save again soon.';
    } else if (!removedPosted || currentDraftId !== draftId) {
      storageNote = ' The separate new-entry draft could not be verified or removed and may appear again.';
    }
  } else if (!removedPosted) {
    storageNote = ' The saved browser copy could not be removed and may appear again.';
  }
  watchRevision();
  showNotice('Saved as ' + saved.path + '.' + storageNote, Boolean(storageNote));
  let data = null;
  try {
    data = await world.get('/entry', { path: saved.path });
  } catch (_) {
    // The entry is saved and open; its links and backlinks arrive on the next refresh.
  }
  if (state.current !== saved.path) return true;
  if (data) {
    renderMetadataSummary(data.entry);
    renderBacklinks(data.backlinks || [], openEntry);
    setEntryLinks(data.links, data.generation, data.entry);
    noteGeneration(data.generation, true);
    renderWords(data.entry);
  }
  emit(Events.ENTRY_OPENED, {
    path: state.current, title: $('entryTitle').textContent,
    entry: (data && data.entry) || null, links: (data && data.links) || [],
  });
  emit(Events.DRAFT_CHANGED);
  return true;
}

// -- Wiring ----------------------------------------------------------------

// Preview replaces the textarea on a narrow editor and sits beside it on a
// wide one (the button then reads "Split").
function applyPreviewLayout() {
  const split = $('editorSplit');
  if (split.clientWidth === 0) return; // the desk is hidden; measure when it returns
  const wide = splitFits(window.innerWidth, split.clientWidth);
  const on = state.preview;
  split.classList.toggle('is-split', on && wide);
  $('composeArea').hidden = on && !wide;
  $('previewPane').hidden = !on;
  $('entryPreview').hidden = !on;
  const toggle = $('previewBtn');
  toggle.textContent = previewLabel(wide, on);
  if (wide) toggle.setAttribute('aria-pressed', String(on));
  else toggle.removeAttribute('aria-pressed');
}

// In Split the preview follows the editor, in proportion, one way.
let syncFrame = 0;

function syncPreviewScroll() {
  if (!$('editorSplit').classList.contains('is-split')) return;
  const field = textarea();
  const pane = $('previewPane');
  pane.scrollTop = proportionalScroll(
    field.scrollTop, field.scrollHeight - field.clientHeight, pane.scrollHeight - pane.clientHeight);
}

function scheduleSyncPreviewScroll() {
  if (syncFrame) return;
  const later = typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame : (fn) => setTimeout(fn, 16);
  syncFrame = later(() => {
    syncFrame = 0;
    syncPreviewScroll();
  });
}

function togglePreview() {
  state.preview = !state.preview;
  applyPreviewLayout();
  if (state.preview) {
    emit(Events.DRAFT_CHANGED);
    scheduleSyncPreviewScroll();
  }
}

function addStructuredHeader() {
  const value = $('metadataValue').value.trim();
  if (!value) {
    $('metadataValue').focus();
    return;
  }
  const result = insertHeader(getText(), $('metadataField').value, value);
  if (!result.ok) {
    showNotice(result.error, true);
    return;
  }
  const field = textarea();
  field.value = result.text;
  field.focus();
  field.setSelectionRange(result.caret, result.caret);
  markEdited();
  $('metadataValue').value = '';
}

function addNoteToSelf() {
  const field = textarea();
  const text = field.value;
  const lead = text && text.charAt(text.length - 1) !== '\n' ? '\n' : '';
  field.value = text + lead + '${note to self}\n';
  field.focus();
  field.setSelectionRange(field.value.length, field.value.length);
  markEdited();
}

export function initEditor() {
  $('saveBtn').addEventListener('click', () => saveEntry());
  $('keepDraftBtn').addEventListener('click', keepDraft);
  $('reloadBtn').addEventListener('click', reloadDiskVersion);
  $('replaceBtn').addEventListener('click', replaceReviewedVersion);
  $('reopenRecovery').addEventListener('click', reopenRecovery);
  $('dismissRecovery').addEventListener('click', dismissRecovery);
  $('previewBtn').addEventListener('click', togglePreview);
  $('insertMetadata').addEventListener('click', addStructuredHeader);
  $('insertNote').addEventListener('click', addNoteToSelf);
  // Another part of the desk (the Upkeep queue) saved the open entry: catch
  // up now rather than at the next poll, so typing does not meet a conflict
  // the writer did not cause. checkRevision leaves a dirty draft alone.
  on(Events.VAULT_CHANGED, (detail) => {
    if (detail && detail.path && detail.path === state.current && !saving) checkRevision(state.current);
  });
  textarea().addEventListener('input', markEdited);
  textarea().addEventListener('scroll', scheduleSyncPreviewScroll);
  window.addEventListener('resize', applyPreviewLayout);
  if (typeof ResizeObserver === 'function') new ResizeObserver(applyPreviewLayout).observe($('editorSplit'));
  document.addEventListener('keydown', (event) => {
    const isSave = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's';
    if (isSave && !$('entryPane').hidden) {
      event.preventDefault();
      saveEntry();
    }
  });
}
