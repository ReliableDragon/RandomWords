// Upkeep: housekeeping findings (stubs, unresolved links, spelling drift...).

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { openCreate } from './create.js';
import { driftPairCard } from './drift.js';
import { openEntry } from './editor.js';
import { mentionGroups, mentionTotals, newDismissed } from './mentions.js';
import { createReportView } from './report.js';
import { renderReviewCard } from './review_queue.js';
import { createFromTarget, entryTitle } from './text.js';
import { dismissalSummary, dismissRow } from './triage.js';

const OPEN_LIMIT = 24; // sections longer than this start collapsed

// Sections in the order they are shown; anything the server adds follows.
const LABELS = {
  unlinked_mentions: 'Named but not linked',
  unresolved_links: 'Unresolved links',
  names_without_entry: 'Names without entry',
  ambiguous_links: 'Ambiguous links',
  name_collisions: 'Name collisions',
  spelling_drift: 'Spelling drift',
  stubs: 'Stubs',
  isolated: 'Isolated notes',
  no_inbound: 'No inbound links',
  rework: 'Needs rework',
  notes_to_self: 'Notes to self',
};
const ORDER = Object.keys(LABELS);

// Which dismissals each section can review, and where the server counts them.
const DISMISSALS = {
  unlinked_mentions: { kinds: ['mention', 'target'], count: 'unlinked_mentions', effectNoun: 'mention' },
  names_without_entry: { kinds: ['name'], count: 'names_without_entry' },
  spelling_drift: { kinds: ['drift'], count: 'spelling_drift' },
};

export function sectionLabel(name) {
  return LABELS[name] || name.replace(/_/g, ' ');
}

// Puts known sections first in their usual order, keeping others after.
export function orderSections(sections) {
  const rank = (name) => (ORDER.indexOf(name) < 0 ? ORDER.length : ORDER.indexOf(name));
  return sections
    .map((entry, index) => ({ entry, index }))
    .sort((a, b) => rank(a.entry[0]) - rank(b.entry[0]) || a.index - b.index)
    .map((wrapped) => wrapped.entry);
}

// The report may key sections by name or list them; returns
// [[name, items]] either way.
export function normalizeSections(data) {
  let sections = data.sections || {};
  if (Array.isArray(sections)) {
    sections = sections.reduce((map, section) => {
      map[section.key || section.id || section.title || 'Findings'] = section.items || section.entries || [];
      return map;
    }, {});
  }
  return Object.keys(sections).map((name) => {
    const value = sections[name];
    let items = [];
    if (Array.isArray(value)) items = value;
    else if (value && Array.isArray(value.items)) items = value.items;
    return [name, items];
  });
}

// Names that are also ordinary words (Despite, Water) are rarely entries
// waiting to be written; the server marks them `common` and they start hidden.
// A missing field counts as false.
export function splitCommon(items) {
  const common = items.filter((item) => item.common === true);
  return { shown: items.filter((item) => item.common !== true), common };
}

function findingPath(item) {
  return item.path || item.source_path || item.canonical_path || '';
}

function findingHeading(item) {
  return item.title || item.name || item.phrase || item.target || item.from || item.text || findingPath(item) || 'Finding';
}

function openNote(path) {
  return button('Open note', 'btn btn-small btn-quiet', () => openEntry(path));
}

function actionRow(...buttons) {
  return h('div', { class: 'world-actions report-actions' }, buttons);
}

// -- Cards, one shape per kind of finding ------------------------------------

function unresolvedCard(item) {
  const card = h('article', { class: 'report-card' },
    textNode('h4', '[[' + item.target + ']]'),
    textNode('small', 'Linked from ' + (item.title || findingPath(item)) + ', but no entry has that name.',
      'report-path'));
  card.appendChild(actionRow(
    button('Create entry', 'btn btn-small btn-primary', () => openCreate(createFromTarget(item.target, {
      fromTargets: item.from_targets || [],
    }))),
    findingPath(item) ? openNote(findingPath(item)) : null));
  return card;
}

function nameCard(item, ctx) {
  const sources = item.sources || (item.path ? [item.path] : []);
  const noun = item.count === 1 ? 'time' : 'times';
  const card = h('article', { class: 'report-card' },
    textNode('h4', item.phrase),
    textNode('small', 'Named ' + item.count + ' ' + noun + ' in ' + sources.length
      + (sources.length === 1 ? ' note' : ' notes'), 'report-path'));
  if (item.context) card.appendChild(textNode('p', item.context));
  if (item.line != null) card.appendChild(textNode('small', 'Line ' + item.line, 'report-path'));
  card.appendChild(actionRow(
    button('Create entry', 'btn btn-small btn-primary', () => openCreate({ title: item.phrase })),
    findingPath(item) ? openNote(findingPath(item)) : null,
    item.triage ? button('Not a name', 'btn btn-small btn-quiet', () => dismissRow({
      node: card, triage: item.triage, label: 'Dismissed “' + item.phrase + '”', onChange: ctx.bump,
    })) : null));
  return card;
}

function ambiguousCard(item) {
  const titles = item.candidate_titles || [];
  const candidates = (item.candidates || []).map((path, index) => h('li', null,
    button(titles[index] || path, 'report-entry-link', () => openEntry(path)),
    textNode('small', path, 'report-path')));
  return h('article', { class: 'report-card' },
    textNode('h4', '[[' + item.target + ']] could mean several entries'),
    textNode('small', 'In ' + (item.title || findingPath(item)), 'report-path'),
    h('ul', { class: 'report-candidates' }, candidates),
    actionRow(openNote(findingPath(item))));
}

function collisionCard(item) {
  const label = item.kind === 'path' ? 'Same path, different capitalization' : 'Same name';
  return h('article', { class: 'report-card' },
    textNode('h4', item.name),
    textNode('small', label + ' — ' + (item.entries || []).length + ' entries', 'report-path'),
    h('ul', { class: 'report-candidates' }, (item.entries || []).map((entry) => h('li', null,
      button(entry.title || entryTitle(entry), 'report-entry-link', () => openEntry(entry.path)),
      textNode('small', entry.path + (entry.via ? ' · via ' + entry.via : ''), 'report-path')))));
}

function plainCard(name, item) {
  const path = findingPath(item);
  const heading = findingHeading(item);
  const card = h('article', { class: 'report-card' }, textNode('h4', heading));
  const detail = item.context || item.reason || item.text || item.target || item.message || '';
  if (detail && detail !== heading) card.appendChild(textNode('p', detail));
  if (item.other_path) {
    card.appendChild(button('Open ' + item.to, 'report-entry-link', () => openEntry(item.other_path)));
  }
  if (item.line != null) card.appendChild(textNode('small', 'Line ' + item.line, 'report-path'));
  if (path) card.appendChild(openNote(path));
  return card;
}

function findingCard(name, item, ctx) {
  if (name === 'unresolved_links') return unresolvedCard(item);
  if (name === 'names_without_entry') return nameCard(item, ctx);
  if (name === 'ambiguous_links') return ambiguousCard(item);
  if (name === 'name_collisions') return collisionCard(item);
  if (name === 'spelling_drift' && item.from) return driftPairCard(item, ctx.bump);
  return plainCard(name, item);
}

// -- Sections ----------------------------------------------------------------

// "Show all N" reveals lowercase and already-linked mentions. Kept across
// reloads so a refresh does not fold the list back up.
let showAllMentions = false;
// Likewise for "Show N common words" under Names without entry.
let showCommonNames = false;

// The list has one row per note and entry (see mentions.js), so its counts
// are of those rows; a dismissal moves them by the rows it takes away.
function mentionsBody(data, ctx) {
  const groups = h('div', { class: 'mention-groups' });
  const dismissed = newDismissed();
  const totals = mentionTotals((data.sections && data.sections.unlinked_mentions) || []);
  const toggle = button('', 'text-button mention-toggle', () => {
    showAllMentions = !showAllMentions;
    paintGroups();
  });
  function paintToggle() {
    toggle.textContent = showAllMentions ? 'Show only linkable' : 'Show all ' + totals.rows;
    toggle.setAttribute('aria-pressed', showAllMentions ? 'true' : 'false');
    toggle.hidden = !showAllMentions && totals.rows <= totals.actionable;
  }
  function paintGroups() {
    paintToggle();
    const list = mentionGroups(data, showAllMentions, onChange, dismissed);
    groups.replaceChildren(...(list.length ? list : [textNode('p', 'Nothing to link.', 'muted')]));
  }
  function onChange(change) {
    totals.rows = Math.max(0, totals.rows + change.rows);
    totals.actionable = Math.max(0, totals.actionable + change.actionable);
    paintToggle();
    ctx.bumpBoth(change);
  }
  paintGroups();
  const intro = textNode('p', 'Notes that mention another entry by name without linking to it. '
    + 'Stage link puts the link in the note for you to review; nothing is saved until you save.', 'muted');
  return [intro, toggle, groups];
}

// The cards for names with no entry, with the common words behind a toggle.
// `ctx.bump` keeps the section count in step as they are shown or hidden.
function namesBody(items, ctx) {
  const { shown, common } = splitCommon(items);
  const list = h('div', { class: 'names-list' });
  const toggle = button('', 'text-button mention-toggle', () => {
    showCommonNames = !showCommonNames;
    ctx.setCount(showCommonNames ? common.length : -common.length);
    paint();
  });
  function paint() {
    const visible = showCommonNames ? items : shown;
    toggle.textContent = showCommonNames
      ? 'Hide common words'
      : 'Show ' + common.length + ' common ' + (common.length === 1 ? 'word' : 'words');
    toggle.setAttribute('aria-pressed', showCommonNames ? 'true' : 'false');
    toggle.hidden = !common.length;
    list.replaceChildren(...(visible.length
      ? visible.map((item) => nameCard(item, ctx))
      : [textNode('p', 'Nothing to review.', 'muted')]));
  }
  paint();
  return [toggle, list];
}

function findingSection(name, items, data) {
  const counts = data.counts || {};
  let count = counts[name] == null ? items.length : counts[name];
  if (name === 'unlinked_mentions' && items.length) count = mentionTotals(items).actionable;
  if (name === 'names_without_entry' && !showCommonNames) count = Math.max(0, count - splitCommon(items).common.length);
  const countNode = textNode('span', count, 'report-count');
  const open = items.length <= OPEN_LIMIT || name === 'unlinked_mentions';
  const section = h('details', { class: 'report-section', open, dataset: { key: name } },
    h('summary', { class: 'report-section-heading' }, textNode('h3', sectionLabel(name)), countNode));
  const bump = (delta) => {
    count = Math.max(0, count + delta);
    countNode.textContent = count;
  };
  const config = DISMISSALS[name];
  let summary = null;
  if (config) {
    // `dismissals` counts what was dismissed; `dismissed` what that hides.
    const hidden = (data.dismissed || {})[config.count];
    const made = (data.dismissals || {})[config.count];
    summary = dismissalSummary({
      kinds: config.kinds,
      count: made == null ? hidden : made,
      effect: made == null ? null : hidden,
      effectNoun: config.effectNoun,
      onRestored: () => upkeep.load({ force: true }),
    });
    section.appendChild(summary.element);
  }
  // Dismissing (-1) or undoing (+1) moves the count and the "dismissed" total.
  const ctx = {
    setCount: bump, // the count alone, for showing or hiding rows
    bump: (delta) => { bump(delta); if (summary) summary.bump(delta); },
    bumpBoth: (change) => {
      bump(change.actionable);
      if (summary) summary.bump(change.dismissals, change.occurrences);
    },
  };
  if (!items.length) section.appendChild(textNode('p', 'Nothing to review.', 'muted'));
  else if (name === 'unlinked_mentions') section.append(...mentionsBody(data, ctx).filter(Boolean));
  else if (name === 'names_without_entry') section.append(...namesBody(items, ctx));
  else items.forEach((item) => section.appendChild(findingCard(name, item, ctx)));
  return section;
}

function renderUpkeep(data) {
  const host = $('upkeepContent');
  const sections = orderSections(normalizeSections(data));
  if (!sections.length) {
    host.replaceChildren(textNode('p', 'No upkeep findings.', 'muted'));
    return;
  }
  // The queue goes through the same report, so it reloads it after a save.
  // A background reload keeps the screen if /health fails after the save went
  // through; `loading` tells the queue another load is still on its way.
  const queue = renderReviewCard(data, {
    reload: () => upkeep.load({ force: true, background: true }),
    loading: () => $('upkeepContent').dataset.loaded === 'loading',
  });
  host.replaceChildren(queue, ...sections.map(([name, items]) => findingSection(name, items, data)));
}

export const upkeep = createReportView({
  hostId: 'upkeepContent',
  loadingText: 'Loading upkeep…',
  getData: () => world.get('/health'),
  render: renderUpkeep,
});

export const load = upkeep.load;
