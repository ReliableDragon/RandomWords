// A tiny publish/subscribe bus so modules can react to each other without
// importing each other. Listener errors are logged, not propagated.

export const Events = {
  // {path}: an entry open was requested. This outdates pending asynchronous
  // draft creation without clearing the editor before the transition is safe.
  ENTRY_OPEN_REQUESTED: 'entry:open-requested',
  // The editor is about to load another entry.
  ENTRY_OPENING: 'entry:opening',
  // {path, title, entry, links}: an entry finished opening in the editor.
  // `entry` is the parsed entry from /api/world/entry (or null) and `links`
  // its link statuses.
  ENTRY_OPENED: 'entry:opened',
  // {path, entry, links}: the open entry's saved data was re-read (after a
  // save, or when the vault moved on), so what describes it may have changed.
  ENTRY_REFRESHED: 'entry:refreshed',
  // The draft text changed (typing, a staged edit, a save) or the preview
  // needs re-analysis.
  DRAFT_CHANGED: 'draft:changed',
  // {path, groups}: fresh Nearby suggestions arrived.
  NEARBY_UPDATED: 'nearby:updated',
  // {path}: a link asked for a reference card instead of opening the entry.
  REFERENCE_REQUESTED: 'reference:requested',
  // {path}: a folder was created in the vault.
  FOLDER_CREATED: 'folder:created',
  // {id}: a new unsaved draft was opened (or resumed) in the editor.
  CREATE_OPENED: 'create:opened',
  // The kept-word list on the bench changed.
  KEPT_CHANGED: 'kept:changed',
  // {generation, path}: this page saved or created a note, so the server's
  // index generation moved on.
  VAULT_CHANGED: 'vault:changed',
};

const listeners = new Map();

export function on(name, listener) {
  if (!listeners.has(name)) listeners.set(name, new Set());
  listeners.get(name).add(listener);
  return () => listeners.get(name).delete(listener);
}

export function emit(name, detail) {
  Array.from(listeners.get(name) || []).forEach((listener) => {
    try {
      listener(detail);
    } catch (error) {
      console.error('world event listener failed for ' + name, error);
    }
  });
}
