// Saves one small replacement in a note without opening it in the editor.
//
// The review queue uses this for "Link and save" and "Fix and save". It follows
// the same rules as the editor's staged replacements (see
// editor.js stageReplacement): the span is only edited when the note's
// revision and the text at the span still match what the report saw, and the
// write carries the revision it read, so a change made meanwhile is a 409
// rather than an overwrite.

import { world } from './api.js';
import { emit, Events } from './events.js';
import { replaceSpan, spanIsCurrent } from './spans.js';
import { state } from './state.js';
import { detectLineEnding, textareaText, toDiskText } from './text.js';

// True when the editor holds unsaved changes to this note; saving behind its
// back would leave the editor on a revision that no longer exists.
export function editorHoldsUnsaved(path) {
  return state.current === path && state.dirty;
}

export const DIRTY_MESSAGE = 'This note has unsaved changes in the editor, so it opens there instead of saving behind it.';
export const STALE_MESSAGE = 'This note changed since Upkeep loaded, so nothing was saved.';
export const CONFLICT_MESSAGE = 'This note was saved somewhere else a moment ago, so nothing was saved.';

// span: {path, revision, start, end, expected}, offsets in the editor's text
// (newlines normalized), as the reports give them. Resolves to
// {status: 'saved', revision, generation} or {status, message} where status
// is 'dirty', 'stale', 'conflict' or 'error'. Never throws.
export async function quickApply(span, replacement) {
  if (editorHoldsUnsaved(span.path)) return { status: 'dirty', message: DIRTY_MESSAGE };
  let data;
  try {
    data = await world.get('/entry', { path: span.path });
  } catch (error) {
    return { status: 'error', message: error.message };
  }
  // The writer may have started typing in this note while it loaded.
  if (editorHoldsUnsaved(span.path)) return { status: 'dirty', message: DIRTY_MESSAGE };
  const text = textareaText(data.text);
  if (!spanIsCurrent({ revision: data.revision, text }, span)) {
    return { status: 'stale', message: STALE_MESSAGE };
  }
  const next = replaceSpan(text, span.start, span.end, replacement);
  try {
    const saved = await world.post('/entry', {
      path: span.path,
      text: toDiskText(next, detectLineEnding(data.text)),
      revision: data.revision,
    });
    emit(Events.VAULT_CHANGED, { generation: saved.generation, path: span.path });
    return { status: 'saved', revision: saved.revision, generation: saved.generation };
  } catch (error) {
    if (error.status === 409) return { status: 'conflict', message: CONFLICT_MESSAGE };
    return { status: 'error', message: error.message };
  }
}
