// State shared between modules. State used by one module lives in that module.

import { prospectivePath } from './draft_text.js';

export const state = {
  // Path of the entry open in the editor, or null. A new, unsaved entry has
  // no path: `current` is null and `newDraft` describes it instead.
  current: null,
  // The unsaved new entry open in the editor, or null:
  // {id, title, folder, folderSource, kind, template, insertedTemplate,
  //  fromTargets: [{path, title}], idea, again}. `folder` is null until one
  // is chosen ('' is the vault root). Its text lives in the textarea.
  newDraft: null,
  // Revision the server reported for the open entry.
  revision: null,
  // The editor text as last loaded from or saved to disk (\n endings).
  savedText: '',
  // Line ending the file uses on disk: '\n', '\r\n' or '\r'.
  lineEnding: '\n',
  // True while the editor text differs from savedText.
  dirty: false,
  // True while the rendered preview replaces the textarea.
  preview: false,
  // Pending save conflict: {text, currentText, currentRevision, lineEnding}.
  conflict: null,
  // Vault identifier reported by the tree route, when known.
  vaultId: null,
  // Latest Nearby response for the open entry.
  nearby: null,
  // Words kept on the bench, and the last words drawn.
  kept: [],
  drawn: [],
  // A backlog idea whose strike-through failed after its entry was created.
  retryIdea: null,
};

// The path Nearby should read the draft as: the open entry's, or where the
// new draft would be saved (Draft.md until it has a folder).
export function nearbyPath() {
  if (state.current) return state.current;
  return state.newDraft ? prospectivePath(state.newDraft) : null;
}
