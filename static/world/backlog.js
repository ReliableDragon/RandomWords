// Backlog: ideas waiting to become entries, plus the "Roll a prompt" card.

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { openCreate } from './create.js';
import { openEntry } from './editor.js';
import { setWorldView } from './nav.js';
import { createReportView } from './report.js';
import { entryTitle, ideaSeedTitle } from './text.js';

function ideaActions(idea) {
  if (idea.done) return button('Open idea', 'btn btn-small btn-quiet', () => openEntry(idea.path));
  return button('Start an entry', 'btn btn-small btn-primary', () => {
    openCreate({ title: ideaSeedTitle(idea.expected), idea });
  });
}

function ideaCard(idea) {
  return h('article', { class: 'report-card backlog-idea' + (idea.done ? ' is-done' : '') },
    textNode('p', idea.expected || idea.text || idea.title || idea.path, 'backlog-idea-text'),
    textNode('small', idea.path, 'report-path'),
    h('div', { class: 'world-actions' }, ideaActions(idea)));
}

function renderBacklog(data) {
  const host = $('backlogContent');
  const ideas = data.ideas || [];
  if (!ideas.length) {
    host.replaceChildren(textNode('p', 'No backlog ideas were found.', 'muted'));
    return;
  }
  host.replaceChildren(...ideas.map(ideaCard));
}

export const backlog = createReportView({
  hostId: 'backlogContent',
  loadingText: 'Loading ideas…',
  getData: () => world.get('/backlog'),
  render: renderBacklog,
});

export const load = backlog.load;

// -- Roll a prompt -----------------------------------------------------------

function rollEntries(entries) {
  const box = h('div', { class: 'roll-entries' });
  entries.forEach((item, index) => {
    if (index) box.appendChild(textNode('span', '×', 'roll-times'));
    box.appendChild(button(item.title || entryTitle(item), 'report-entry-link roll-entry', () => openEntry(item.path)));
  });
  return box;
}

function rolledEntries(result) {
  const entry = result.entry;
  return Array.isArray(entry) ? entry : (entry ? [entry] : []);
}

// The wikilink to a rolled entry: the server's `link` (its title when that
// names it alone, else its qualified path), labelled with the title.
export function rollLink(item) {
  const title = item.title || entryTitle(item);
  const target = String(item.link || item.path || title).replace(/\.md$/i, '');
  return '[[' + target + (target === title ? '' : '|' + title) + ']]';
}

// What "Start entry from this roll" hands the create form: the rolled words
// as seeds, the first entry's places as From targets, and a first draft that
// links what was rolled under a heading for the facet.
export function rollStart(result) {
  const entries = rolledEntries(result);
  const links = entries.map(rollLink);
  const intro = links.length > 1 ? links.join(' × ') : (links.length ? 'Relates to ' + links[0] : '');
  const body = [intro, result.facet ? '## ' + result.facet : ''].filter(Boolean).join('\n\n');
  return {
    seeds: (result.words || []).map((word) => ({ word, gloss: '' })),
    fromTargets: entries.length ? (entries[0].from_targets || []) : [],
    body: body ? body + '\n\n' : '',
  };
}

function renderRoll(result) {
  const card = $('rollCard');
  const entries = rolledEntries(result);
  const words = result.words || [];
  card.replaceChildren(textNode('p', result.facet || 'Writing prompt', 'eyebrow'), rollEntries(entries));
  card.hidden = false;
  card.className = 'roll-card';
  if (words.length) card.appendChild(textNode('p', words.join(' · '), 'roll-words'));
  card.appendChild(h('div', { class: 'world-actions' },
    button('Start entry from this roll', 'btn btn-small btn-primary', () => openCreate(rollStart(result)))));
}

// Rolls a prompt and shows it on the Backlog view. `options.entry` (a vault
// path) keeps that entry in the prompt; everything else is rolled.
export async function rollPrompt(options = {}) {
  const card = $('rollCard');
  const body = options.entry ? { entry: options.entry } : {};
  setWorldView('backlog');
  card.hidden = false;
  card.replaceChildren(textNode('p', 'Rolling…', 'muted'));
  try {
    renderRoll(await world.post('/roll', body));
  } catch (error) {
    card.replaceChildren(textNode('p', error.message, 'tree-error'));
  }
}

export function initBacklog() {
  $('rollPrompt').addEventListener('click', () => rollPrompt());
}
