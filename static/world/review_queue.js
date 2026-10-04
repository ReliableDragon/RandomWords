// Upkeep's review queue: the highest-value findings, one at a time, in place.
//
// The queue is built from the health report (see buildQueue) and never leaves
// Upkeep: "Link and save" and "Fix and save" go through quick_edit.js, and the
// dismissals are the ones the sections below already offer. After anything that
// changes the vault the report is reloaded, so the next item always carries
// fresh offsets and revisions. The session (tally, skipped items) lives here
// and survives those reloads.

import { button, h, textNode } from './dom.js';
import { openCreate } from './create.js';
import { openEntry, stageReplacement } from './editor.js';
import { collidingPaths, groupMentions, mentionLink, splitContext } from './mentions.js';
import { activeView as currentView } from './nav.js';
import { quickApply } from './quick_edit.js';
import { dismiss, restore } from './triage.js';
import { createFromTarget, entryTitle } from './text.js';

const UNDO_MS = 6000;
const STUB_LIMIT = 8;
const NOTE_LIMIT = 8;

// Seconds a writer needs for one item of each kind; only for the estimate.
const SECONDS = { mention: 10, unresolved: 25, drift: 10, stub: 60, note: 40 };

// -- Pure helpers ------------------------------------------------------------

function sentence(before, match, after, proposed) {
  return { before: before || '', match: match || '', after: after || '', proposed: proposed == null ? null : proposed };
}

// Mentions worth a click: exact case, not already linked, one per note and
// target (linking the first mention makes the rest "already linked"), grouped
// by target with the most widely named target first.
function mentionItems(data) {
  const rows = (data.sections && data.sections.unlinked_mentions) || [];
  const colliding = collidingPaths(data.sections && data.sections.name_collisions);
  const items = [];
  groupMentions(rows, data.mention_counts).forEach((group) => {
    group.actionable.filter((row) => row.exact_case).forEach((row) => {
      const [before, match, after] = splitContext(row.context, row.text);
      const link = mentionLink(row, colliding);
      items.push({
        key: 'm|' + row.source_path + '|' + row.target_path,
        type: 'mention',
        group: { key: 'm|' + group.target_path, label: group.target_title, noun: 'note' },
        path: row.source_path,
        title: row.source_title || entryTitle({ path: row.source_path }),
        line: row.line,
        sentence: sentence(before, match || row.text, after, link),
        span: { path: row.source_path, revision: row.source_revision, start: row.start, end: row.end, expected: row.text },
        replacement: link,
        highlight: { start: row.start, end: row.end },
        dismissals: [
          row.triage ? { label: 'Not in this note', summary: 'Hidden for this note', triage: row.triage } : null,
          row.target_triage
            ? { label: 'Never suggest', summary: 'Won’t suggest ' + group.target_title, triage: row.target_triage, quiet: true }
            : null,
        ].filter(Boolean),
      });
    });
  });
  return items;
}

function unresolvedItems(data) {
  return ((data.sections && data.sections.unresolved_links) || []).map((row) => ({
    key: 'u|' + row.path + '|' + row.target + '|' + row.link_index,
    type: 'unresolved',
    group: { key: 'cat:unresolved', label: 'Unresolved links', noun: 'link' },
    path: row.path,
    title: row.title || entryTitle({ path: row.path }),
    detail: '[[' + row.target + ']] has no entry with that name.',
    create: createFromTarget(row.target, { fromTargets: row.from_targets || [] }),
    dismissals: [],
  }));
}

function driftItems(data) {
  const items = [];
  ((data.sections && data.sections.spelling_drift) || []).forEach((pair) => {
    if (!pair.from) return;
    (pair.occurrences || []).forEach((use) => {
      const replacement = use.replacement || pair.to;
      items.push({
        key: 'd|' + pair.from + '|' + pair.to + '|' + use.path + '|' + use.start,
        type: 'drift',
        group: { key: 'd|' + pair.from + '|' + pair.to, label: pair.from + ' → ' + pair.to, noun: 'place' },
        path: use.path,
        title: entryTitle({ path: use.path }),
        line: use.line,
        sentence: sentence(use.context_before, use.spelling, use.context_after, replacement),
        span: { path: use.path, revision: use.revision, start: use.start, end: use.end, expected: use.spelling },
        replacement,
        highlight: { start: use.start, end: use.end },
        dismissals: pair.triage
          ? [{ label: 'Not drift', summary: 'Dismissed ' + pair.from + ' / ' + pair.to, triage: pair.triage }]
          : [],
      });
    });
  });
  return items;
}

// Stubs the rest of the vault names most often come first. The report does not
// count inbound links per stub, so the number of notes naming it unlinked
// (mention_counts) stands in for it.
function stubItems(data) {
  const named = {};
  (data.mention_counts || []).forEach((row) => { named[row.target_path] = row.notes || 0; });
  const stubs = ((data.sections && data.sections.stubs) || []).map((row, index) => ({ row, index }));
  stubs.sort((a, b) => (named[b.row.path] || 0) - (named[a.row.path] || 0)
    || (b.row.words || 0) - (a.row.words || 0) || a.index - b.index);
  return stubs.slice(0, STUB_LIMIT).map(({ row }) => ({
    key: 's|' + row.path,
    type: 'stub',
    group: { key: 'cat:stub', label: 'Stubs', noun: 'note' },
    path: row.path,
    title: row.title || entryTitle({ path: row.path }),
    detail: stubDetail(row, named[row.path] || 0),
    dismissals: [],
  }));
}

export function stubDetail(row, namedIn) {
  const words = row.words == null ? '' : row.words + (row.words === 1 ? ' word' : ' words');
  const named = namedIn ? 'named without a link in ' + namedIn + (namedIn === 1 ? ' note' : ' notes') : '';
  return [words, named].filter(Boolean).join(' · ') || 'Short note';
}

function noteItems(data) {
  return ((data.sections && data.sections.notes_to_self) || []).slice(0, NOTE_LIMIT).map((row) => {
    const [before, match, after] = splitContext(row.context, '${' + row.text + '}');
    return {
      key: 'n|' + row.path + '|' + row.line + '|' + row.text,
      type: 'note',
      group: { key: 'cat:note', label: 'Notes to self', noun: 'note' },
      path: row.path,
      title: row.title || entryTitle({ path: row.path }),
      line: row.line,
      sentence: sentence(before, match, after, null),
      dismissals: [],
    };
  });
}

// Every item in review order: named-but-not-linked mentions (by target), then
// unresolved links, spelling drift, the most-named stubs and notes to self.
// `skipped` is a Set of item keys to leave out. `focusGroup` is the group the
// writer is in the middle of: it stays in front, because linking one note
// lowers that target's note count and would otherwise let another target
// overtake it half way through.
export function buildQueue(data, skipped, focusGroup) {
  const passed = skipped || new Set();
  const items = [].concat(mentionItems(data), unresolvedItems(data), driftItems(data), stubItems(data), noteItems(data))
    .filter((item) => !passed.has(item.key));
  if (!focusGroup) return items;
  return items.filter((item) => item.group.key === focusGroup)
    .concat(items.filter((item) => item.group.key !== focusGroup));
}

export function estimateMinutes(items) {
  const seconds = items.reduce((sum, item) => sum + (SECONDS[item.type] || 30), 0);
  return Math.max(1, Math.round(seconds / 60));
}

export function queueSummary(items) {
  const n = items.length;
  const minutes = estimateMinutes(items);
  return n + (n === 1 ? ' suggestion' : ' suggestions') + ', about ' + minutes + (minutes === 1 ? ' minute' : ' minutes');
}

// Where the writer is inside the item's group: "Hozon · note 2 of 6". `done`
// maps a group key to how many of its items were handled this session.
export function groupProgress(item, items, done) {
  const finished = (done && done[item.group.key]) || 0;
  const left = items.filter((other) => other.group.key === item.group.key).length;
  const total = finished + left;
  return {
    index: finished + 1,
    total,
    label: item.group.label + ' · ' + item.group.noun + ' ' + (finished + 1) + ' of ' + total,
    fraction: total ? finished / total : 0,
  };
}

export function newSession() {
  return {
    active: false,
    passed: new Set(), // keys skipped or opened this session
    done: {}, // group key -> items handled
    tally: { linked: 0, fixed: 0, skipped: 0, dismissed: 0, opened: 0 },
    undo: null, // {item, dismissal, timer}
    notice: null, // {text, error, item}
    busy: false,
    pinned: null, // an item to show next, e.g. one brought back by Undo
    focusGroup: null, // the group being worked through; see buildQueue
    focusPending: false, // the writer just acted: move focus to the card once it is idle
  };
}

// "8 linked · 3 skipped · 2 dismissed"; empty before anything was done.
export function tallyText(tally) {
  return ['linked', 'fixed', 'skipped', 'dismissed', 'opened']
    .filter((name) => tally[name] > 0)
    .map((name) => tally[name] + ' ' + name)
    .join(' · ');
}

export function sessionHandled(session) {
  return Object.keys(session.tally).some((name) => session.tally[name] > 0);
}

// Whether a key event's target belongs to the queue card: something inside it,
// or the page itself (body) when nothing else has focus.
export function ownsKey(target, card, pageNodes) {
  if (!target || (pageNodes || []).indexOf(target) >= 0) return true;
  for (let node = target; node; node = node.parentNode) {
    if (node === card) return true;
  }
  return false;
}

// The key shortcut for an event: 'primary' (Enter), 'skip' (S), 'leave' (Esc)
// or null. Keys typed into a field belong to the field; buttons, links and
// <summary> have their own Enter and Space. `scope` says where the queue is:
//   drawerOpen  the word generator drawer covers the desk, so keys are its own
//   owns(node)  true for a target inside the queue card (or the bare page)
// Only the visible Upkeep view, with the queue as the target, ever acts.
export function keyAction(event, view, scope) {
  if (view !== 'upkeep' || event.defaultPrevented) return null;
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  const where = scope || {};
  if (where.drawerOpen || !where.owns) return null;
  const target = event.target || {};
  if (!where.owns(event.target)) return null;
  const tag = String(target.tagName || '').toLowerCase();
  const own = tag === 'input' || tag === 'textarea' || tag === 'select' || tag === 'button' || tag === 'a'
    || tag === 'summary' || Boolean(target.isContentEditable);
  if (own) return null;
  if (event.key === 'Escape') return 'leave';
  if (event.key === 'Enter') return 'primary';
  if (event.key === 's' || event.key === 'S') return 'skip';
  return null;
}

// -- Session and card --------------------------------------------------------

export const session = newSession();

// What the key handler drives; set by the card most recently rendered.
let controller = null;
let keysBound = false;

// Counts the cards built from report data. After a save the old card must not
// come back until a card from data newer than the save has been rendered.
let renderGeneration = 0;
let renderWaiters = [];
export const timing = { renderWaitMs: 10000 };

// Resolves true once a card is rendered after `since`, false after the wait.
function nextRender(since) {
  if (renderGeneration > since) return Promise.resolve(true);
  return new Promise((resolve) => {
    const waiter = { resolve, timer: setTimeout(() => {
      renderWaiters = renderWaiters.filter((item) => item !== waiter);
      resolve(false);
    }, timing.renderWaitMs) };
    renderWaiters.push(waiter);
  });
}

function noteRender() {
  renderGeneration += 1;
  const waiting = renderWaiters;
  renderWaiters = [];
  waiting.forEach((waiter) => { clearTimeout(waiter.timer); waiter.resolve(true); });
}

// The document's key handler; exported so the tests can call it directly.
export function handleKeydown(event) {
  if (!controller || !session.active) return;
  const drawer = document.getElementById && document.getElementById('generatorDrawer');
  const page = [document.body, document.documentElement];
  const action = keyAction(event, currentView(), {
    drawerOpen: Boolean(drawer && !drawer.hidden),
    owns: (target) => controller.attached() && ownsKey(target, controller.card, page),
  });
  if (!action || !controller[action]) return;
  event.preventDefault();
  controller[action]();
}

function bindKeys() {
  if (keysBound || typeof document === 'undefined' || !document.addEventListener) return;
  keysBound = true;
  document.addEventListener('keydown', handleKeydown);
}

const CATEGORY_LABELS = {
  mention: 'Named but not linked',
  unresolved: 'Unresolved link',
  drift: 'Spelling drift',
  stub: 'Stub',
  note: 'Note to self',
};

function sentenceView(item) {
  const s = item.sentence;
  const parts = [s.before];
  if (s.match && s.proposed != null) {
    parts.push(textNode('del', s.match, 'review-del'), textNode('ins', s.proposed, 'review-ins'));
  } else if (s.match) {
    parts.push(textNode('mark', s.match, 'drift-token'));
  }
  parts.push(s.after);
  return h('p', { class: 'review-sentence' }, parts);
}

function itemBody(item) {
  if (item.sentence) return sentenceView(item);
  return textNode('p', item.detail || '', 'review-sentence');
}

// The primary action's label for each kind of item.
export function primaryLabel(item) {
  if (item.type === 'mention') return 'Link and save';
  if (item.type === 'drift') return 'Fix and save';
  if (item.type === 'unresolved') return 'Create entry';
  return 'Open in editor';
}

function openLocation(item) {
  return openEntry(item.path, item.highlight ? { highlight: item.highlight } : undefined);
}

// `ctx.reload()` reloads the report and resolves once it has re-rendered.
export function renderReviewCard(data, ctx) {
  bindKeys();
  const card = h('section', { class: 'review-queue', 'aria-label': 'Review queue' });
  let items = buildQueue(data, session.passed);

  function current() {
    if (session.pinned) return session.pinned;
    return items[0] || null;
  }

  function paint() {
    items = buildQueue(data, session.passed, session.focusGroup);
    const item = session.active ? current() : null;
    card.replaceChildren(session.active ? (item ? itemView(item) : doneView()) : idleView());
    // Focus moves only after the writer's own action (Start reviewing, a save,
    // a skip...), so a background reload never pulls it off what they are
    // reading. Once focused, keys (Enter, S, Esc) work without clicking first.
    if (session.active && !session.busy && session.focusPending) {
      session.focusPending = false;
      setTimeout(focusStage, 0);
    }
  }

  // After a change to the vault: reload, and the fresh data repaints the card
  // (the report re-renders, which builds a new card from the session). The
  // save also makes freshness start a reload of its own, which supersedes ours
  // and resolves it without rendering, so the card stays busy until a card
  // built from data newer than the save has actually been rendered.
  async function afterChange() {
    const since = renderGeneration;
    try {
      await ctx.reload();
    } catch (_) {
      // The reload failed; the card on screen stays usable.
    }
    const loading = ctx.loading && ctx.loading();
    if (renderGeneration === since && loading) await nextRender(since);
    if (renderGeneration > since) session.notice = null;
    session.busy = false;
    // The reload re-rendered the report, so the live card is a newer one.
    if (controller) controller.repaint();
    else paint();
  }

  function leave() {
    session.active = false;
    session.focusPending = false;
    session.pinned = null;
    paint();
  }

  function pass(item, tallyName) {
    session.passed.add(item.key);
    session.focusGroup = item.group.key;
    session.done[item.group.key] = (session.done[item.group.key] || 0) + 1;
    session.tally[tallyName] += 1;
    if (session.pinned && session.pinned.key === item.key) session.pinned = null;
    session.notice = null;
  }

  function skip(item) {
    if (session.busy) return;
    pass(item, 'skipped');
    session.focusPending = true;
    paint();
  }

  async function primary(item) {
    if (session.busy) return;
    if (item.type === 'mention' || item.type === 'drift') {
      await save(item);
    } else if (item.type === 'unresolved') {
      pass(item, 'opened');
      paint();
      openCreate(item.create);
    } else {
      pass(item, 'opened');
      paint();
      openLocation(item);
    }
  }

  async function save(item) {
    session.busy = true;
    session.focusPending = true;
    session.notice = null;
    paint();
    const outcome = await quickApply(item.span, item.replacement);
    if (outcome.status === 'saved') {
      pass(item, item.type === 'drift' ? 'fixed' : 'linked');
      await afterChange();
      return;
    }
    session.busy = false;
    if (outcome.status === 'dirty') {
      // The editor holds this note's unsaved text: stage the change there.
      pass(item, 'opened');
      session.notice = { text: outcome.message, error: false };
      paint();
      stageReplacement(item.span, item.replacement, {
        stale: 'That text changed in the editor. Review the note and make the change by hand.',
        staged: 'Change staged. Review the highlighted text, then save.',
      });
      return;
    }
    session.notice = { text: outcome.message, error: true, item };
    paint();
  }

  async function dismissItem(item, dismissal) {
    if (session.busy) return;
    session.busy = true;
    session.focusPending = true;
    session.notice = null;
    paint();
    try {
      await dismiss(dismissal.triage);
    } catch (error) {
      session.busy = false;
      session.notice = { text: error.message, error: true, item };
      paint();
      return;
    }
    pass(item, 'dismissed');
    clearTimeout(session.undo && session.undo.timer);
    const record = { item, dismissal, timer: null };
    record.timer = setTimeout(() => {
      if (session.undo === record) session.undo = null;
      // The report may have re-rendered since: repaint whichever card is live.
      if (controller) controller.repaint();
    }, UNDO_MS);
    session.undo = record;
    await afterChange();
  }

  async function undoDismissal() {
    const record = session.undo;
    if (!record || session.busy) return;
    clearTimeout(record.timer);
    session.busy = true;
    session.focusPending = true;
    paint();
    try {
      await restore(record.dismissal.triage);
    } catch (error) {
      session.busy = false;
      session.notice = { text: error.message, error: true };
      session.undo = null;
      paint();
      return;
    }
    session.undo = null;
    session.passed.delete(record.item.key);
    session.tally.dismissed = Math.max(0, session.tally.dismissed - 1);
    const group = record.item.group.key;
    session.done[group] = Math.max(0, (session.done[group] || 0) - 1);
    session.pinned = record.item;
    await afterChange();
  }

  // -- Views ---------------------------------------------------------------

  function tallyLine() {
    const text = tallyText(session.tally);
    return text ? textNode('p', text, 'review-tally') : null;
  }

  function undoStrip() {
    if (!session.undo) return null;
    return h('div', { class: 'triage-undo review-undo', role: 'status' },
      textNode('span', session.undo.dismissal.summary + ' · ', 'muted'),
      button('Undo', 'text-button', undoDismissal));
  }

  function idleView() {
    const resumable = sessionHandled(session) && items.length > 0;
    const heading = items.length ? queueSummary(items) : 'Nothing to review';
    const lead = items.length
      ? 'The most useful fixes first, one at a time, without leaving Upkeep. The full lists are below.'
      : (sessionHandled(session)
        ? 'You have been through everything the queue holds.'
        : 'No links to add, spelling to fix or notes to tidy right now. The full lists are below.');
    const actions = h('div', { class: 'world-actions review-actions' });
    if (items.length) {
      actions.appendChild(button(resumable ? 'Resume reviewing' : 'Start reviewing', 'btn btn-primary', () => {
        session.active = true;
        session.focusPending = true;
        paint();
      }));
    }
    if (sessionHandled(session) || session.passed.size) {
      actions.appendChild(button('Start over', 'btn btn-quiet', () => {
        Object.assign(session, newSession());
        paint();
      }));
    }
    return h('div', { class: 'review-idle' },
      h('div', null,
        textNode('p', 'REVIEW QUEUE', 'eyebrow'),
        textNode('p', heading, 'review-heading'),
        textNode('p', lead, 'muted review-lead'),
        tallyLine()),
      actions,
      undoStrip());
  }

  function doneView() {
    return h('div', { class: 'review-done' },
      textNode('p', 'REVIEW QUEUE', 'eyebrow'),
      textNode('p', 'That is everything in the queue', 'review-heading'),
      tallyLine(),
      session.passed.size
        ? textNode('p', 'Skipped and opened items come back when you start over.', 'muted review-lead')
        : null,
      h('div', { class: 'world-actions review-actions' },
        button('Back to the full list', 'btn btn-primary', leave),
        button('Start over', 'btn btn-quiet', () => {
          Object.assign(session, newSession(), { active: true, focusPending: true });
          paint();
        })),
      undoStrip());
  }

  function noticeView() {
    const notice = session.notice;
    if (!notice) return null;
    const node = h('div', { class: 'review-notice' + (notice.error ? ' is-error' : ''), role: 'alert' },
      textNode('span', notice.text));
    if (notice.item) {
      node.appendChild(button('Open in editor', 'btn btn-small btn-primary', () => {
        pass(notice.item, 'opened');
        paint();
        openLocation(notice.item);
      }));
    }
    return node;
  }

  function itemView(item) {
    const progress = groupProgress(item, items, session.done);
    const busy = session.busy;
    const guard = (fn) => () => { if (!session.busy) fn(); };
    const actions = h('div', { class: 'review-actions' });
    const main = button(primaryLabel(item), 'btn btn-primary', guard(() => primary(item)));
    main.disabled = busy;
    const skipButton = button('Skip', 'btn btn-quiet', guard(() => skip(item)));
    skipButton.disabled = busy;
    actions.append(main, skipButton);
    item.dismissals.forEach((dismissal) => {
      const label = dismissal.label === 'Never suggest' ? 'Never suggest ' + item.group.label : dismissal.label;
      const control = button(label, 'btn btn-quiet', guard(() => dismissItem(item, dismissal)));
      control.disabled = busy;
      actions.appendChild(control);
    });
    if (item.type !== 'stub' && item.type !== 'note') {
      const open = button('Open in editor', 'text-button review-open', guard(() => {
        pass(item, 'opened');
        paint();
        openLocation(item);
      }));
      open.disabled = busy;
      actions.appendChild(open);
    }
    const bar = h('div', {
      class: 'review-bar', role: 'progressbar', 'aria-label': progress.label,
      'aria-valuemin': '0', 'aria-valuemax': String(progress.total), 'aria-valuenow': String(progress.index - 1),
    }, h('span', { style: 'width:' + Math.round(progress.fraction * 100) + '%' }));
    return h('div', { class: 'review-active', tabindex: '-1' },
      h('div', { class: 'review-top' },
        textNode('p', 'REVIEW QUEUE · ' + CATEGORY_LABELS[item.type].toUpperCase(), 'eyebrow'),
        button('Leave queue', 'text-button', leave)),
      textNode('p', progress.label, 'review-progress-label'),
      bar,
      h('div', { class: 'review-item' },
        h('p', { class: 'review-note' },
          textNode('strong', item.title),
          item.line != null ? textNode('small', 'line ' + item.line, 'report-path') : null),
        itemBody(item)),
      noticeView(),
      busy ? textNode('p', 'Working…', 'muted review-busy') : actions,
      h('div', { class: 'review-foot' },
        tallyLine(),
        textNode('p', 'Enter ' + primaryLabel(item).toLowerCase() + ' · S skip · Esc leave', 'review-hint')),
      undoStrip());
  }

  function focusStage() {
    if (currentView() !== 'upkeep') return;
    const node = card.querySelector ? card.querySelector('.review-active') : null;
    if (node && node.focus) node.focus({ preventScroll: true });
  }

  controller = {
    primary: () => { const item = session.active && current(); if (item) primary(item); },
    skip: () => { const item = session.active && current(); if (item) skip(item); },
    leave: () => { if (session.active) leave(); },
    repaint: paint,
    card,
    // False once the report has re-rendered and this card was thrown away.
    attached: () => card.isConnected !== false,
  };
  paint();
  noteRender();
  return card;
}
