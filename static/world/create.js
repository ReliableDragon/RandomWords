// Starting an entry: write first, place later.
//
// "Start an entry" opens the normal editor on a new unsaved draft. Where it
// lives (folder, From place, template) is chosen from the placement bar when
// the writer is ready, and the header lines are ordinary text in the draft.
// Saving turns the draft into the entry in place.
//
// Other modules start a draft with openCreate(prefill), for example from a
// backlog idea, a Nearby card or a coverage gap.

import { world } from './api.js';
import { $, button } from './dom.js';
import { linkFor } from './autocomplete.js';
import { appendTemplate, draftIssues, placeTemplate, prefillText } from './draft_text.js';
import {
  addNoticeAction, adoptSavedDraft, discardNewDraft, getText, openEntry, resumeNewDraft, showNewDraft, showNotice,
} from './editor.js';
import { emit, Events, on } from './events.js';
import { offerIdeaRetry } from './idea.js';
import { invalidateView } from './nav.js';
import { activeDraftId, forgetNewDraft, makeDraft, setDraftSaver, startNewDraft } from './new_draft.js';
import {
  clearPlacementIssue, initPlacement, noteFolderUsed, openPlacementPanel, showMissing, showSaveProblem,
} from './placement.js';
import { state } from './state.js';
import { entryTitle, folderParent } from './text.js';
import { loadRoot } from './tree.js';

// The latest openCreate call; a slower, earlier one must not replace it. An
// entry starting to open (ENTRY_OPENING) also outdates any openCreate still
// waiting for its lookups, so a late draft never replaces the note the writer
// has since opened.
let openSequence = 0;
function outdateOpenCreate() { openSequence++; }
let saving = false;

// -- Prefill ---------------------------------------------------------------

// Each From target as {path, title, link}: the [[link]] is the title when no
// other entry shares it, and the qualified path when one does.
async function resolveFromTargets(targets) {
  const wanted = [];
  (targets || []).forEach((target) => {
    const path = typeof target === 'string' ? target : target.path;
    if (!/\.md$/i.test(path || '') || wanted.some((item) => item.path === path)) return;
    wanted.push({ path, title: (typeof target === 'object' && target.title) || entryTitle({ path }) });
  });
  return Promise.all(wanted.map(async (item) => {
    let hits = [];
    try {
      hits = (await world.get('/search', { q: item.title })).results || [];
    } catch (_) {
      // Without the lookup the title is taken as unique.
    }
    return Object.assign({}, item, { link: linkFor({ path: item.path, title: item.title, folder: folderParent(item.path) }, hits) });
  }));
}

async function readTemplate(path) {
  if (!path) return '';
  try {
    return (await world.get('/entry', { path })).text || '';
  } catch (_) {
    return '';
  }
}

async function folderIsThere(folder) {
  if (!folder) return true;
  try {
    await world.get('/tree', { path: folder });
    return true;
  } catch (error) {
    return error.status !== 404;
  }
}

// -- Opening a draft -------------------------------------------------------

// Opens a new draft in the editor. All prefill fields are optional:
//   title       the entry's title (it can stay empty until save)
//   folder      vault folder to place it in (dropped, with a note, if missing)
//   fromTargets canonical .md paths (or {path, title}) for the From: line
//   seeds       [{word, gloss}] for the Origin: line (kept words are added)
//   tags        ['flora', ...]
//   template    a Templates/... path whose headings go in
//   kind        a world kind, shown as chosen in the placement panel
//   body        first-draft text
//   idea        a backlog idea to strike through once the entry exists
// Everything but title, folder, kind and idea becomes text in the draft.
// Words kept on the bench go on the Origin: line. Resolves once it is open.
export async function openCreate(prefill) {
  const options = prefill || {};
  const mine = ++openSequence;
  const [from, templateText, folderOk] = await Promise.all([
    resolveFromTargets(options.fromTargets),
    readTemplate(options.template),
    folderIsThere(options.folder),
  ]);
  if (mine !== openSequence) return; // a later start won
  let text = prefillText(options, from.map((item) => item.link), state.kept);
  const draft = makeDraft({
    title: options.title,
    folder: folderOk ? options.folder : null,
    kind: options.kind,
    template: options.template,
    fromTargets: from.map(({ path, title }) => ({ path, title })),
    idea: options.idea,
  });
  if (templateText.trim()) {
    const placed = placeTemplate(text, templateText, '');
    text = placed.placed ? placed.text : appendTemplate(text, templateText);
    draft.insertedTemplate = templateText;
  }
  startNewDraft(draft, text);
  showNewDraft(text);
  if (!folderOk) {
    openPlacementPanel({
      focus: 'folder',
      message: 'The folder "' + options.folder + '" is not in this vault. Choose another folder.',
    });
  }
}

// -- Saving ----------------------------------------------------------------

function reportIdeaResult(data, idea) {
  if (data.idea_updated !== false) return;
  state.retryIdea = idea || null;
  showNotice(data.idea_error || 'Entry created, but the idea was not struck through.', true);
  offerIdeaRetry();
}

function titleTaken(title, folder) {
  return 'There is already an entry called "' + title + '" in ' + (folder || 'the vault root')
    + '. Give this one another title, such as "' + title + ' 2".';
}

// The draft's text is saved exactly as written (its header lines are already
// in it), so nothing but the folder and title is sent besides the text.
async function saveNewDraft() {
  const draft = state.newDraft;
  if (!draft || saving) return false;
  const issues = draftIssues(draft);
  if (issues.title || issues.folder) {
    showMissing(issues);
    return false;
  }
  const text = getText();
  const title = draft.title.trim();
  const payload = { folder: draft.folder, title, body: text, from_targets: [], origin: [], tags: [], template: null };
  if (draft.idea) payload.idea = draft.idea;
  clearPlacementIssue();
  saving = true;
  try {
    const data = await world.post('/new', payload);
    forgetNewDraft(draft.id);
    emit(Events.VAULT_CHANGED, { generation: data.generation, path: data.path });
    await loadRoot();
    noteFolderUsed(payload.folder);
    if (draft.idea) invalidateView('backlog');
    if (state.newDraft !== draft) {
      // The writer opened something else while this saved.
      showNotice('Saved as ' + data.path + '.');
    } else if (draft.again) {
      await startAnother(draft, data, title);
    } else {
      await adoptSavedDraft({ path: data.path, revision: data.revision, title, text });
    }
    reportIdeaResult(data, draft.idea);
    return true;
  } catch (error) {
    reportSaveError(error, title, draft.folder);
    return false;
  } finally {
    saving = false;
  }
}

function reportSaveError(error, title, folder) {
  if (error.status === 409) {
    showSaveProblem(titleTaken(title, folder), true);
  } else if (error.status === 400 && /folder/i.test(error.message)) {
    openPlacementPanel({ focus: 'folder', message: error.message });
  } else {
    showNotice(error.message, true);
  }
}

// "Create another like this": after saving, a fresh draft with the same
// place, folder and template.
async function startAnother(draft, data, title) {
  await openCreate({
    folder: draft.folder, kind: draft.kind, template: draft.template, fromTargets: draft.fromTargets,
  });
  showNotice('Saved "' + title + '" as ' + data.path + '. This new draft has the same place, folder and template.');
  addNoticeAction(button('Open the saved entry', 'btn btn-small btn-quiet', () => openEntry(data.path)));
}

export function initCreate() {
  $('newEntryBtn').addEventListener('click', () => openCreate());
  $('welcomeNew').addEventListener('click', () => openCreate());
  on(Events.ENTRY_OPENING, outdateOpenCreate);
  setDraftSaver(saveNewDraft);
  initPlacement({ discard: discardNewDraft });
  // Reloading mid-draft brings the draft back where it was.
  const kept = activeDraftId();
  if (kept) resumeNewDraft(kept);
}
