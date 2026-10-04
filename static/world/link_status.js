// The "Links" summary under the editor: wikilinks that do not resolve to one
// entry, with a fix for each. Ambiguous links can be pinned to one candidate
// and unresolved ones can start a new entry.
//
// Statuses come from the server for the saved text; each row is matched
// against the text on screen, and an edit is refused if its span moved.

import { $, button, h, textNode } from './dom.js';
import { openCreate } from './create.js';
import { currentProblems, fromTargetPaths, onMarksChanged } from './draft_marks.js';
import { getText, replaceRange, showNotice } from './editor.js';
import { linkIsCurrent, linkSummary, qualifiedLink } from './editor_marks.js';
import { Events, on } from './events.js';
import { state } from './state.js';
import { displayPath } from './text.js';

const MAX_ROWS = 10;
const RENDER_DELAY_MS = 250;
let timer = null;

function applyCandidate(problem, path) {
  if (!linkIsCurrent(getText(), problem)) {
    showNotice('That link changed. Check the Links list and try again.', true);
    render();
    return;
  }
  replaceRange(problem.start, problem.end, qualifiedLink(problem, path));
}

// [[Places/Harbor]] starts "Harbor" in Places; a bare name starts in the root.
function startEntry(problem) {
  const parts = problem.target.split('/');
  const title = parts.pop().replace(/\.md$/i, '');
  openCreate({ title, folder: parts.join('/'), fromTargets: fromTargetPaths() });
}

function createButton(problem) {
  const create = button('Create entry', 'btn btn-small btn-quiet', () => startEntry(problem));
  create.setAttribute('aria-label', 'Create entry ' + problem.target);
  return create;
}

function candidateButton(problem, path) {
  const choice = button(displayPath(path), 'btn btn-small btn-quiet', () => applyCandidate(problem, path));
  choice.setAttribute('aria-label', 'Link ' + problem.raw + ' to ' + displayPath(path));
  return choice;
}

function problemRow(problem) {
  const label = problem.status === 'ambiguous' ? 'Ambiguous' : 'Unresolved';
  const actions = problem.status === 'ambiguous'
    ? h('div', { class: 'link-candidates' }, textNode('span', 'Link to', 'muted'),
      problem.candidates.map((path) => candidateButton(problem, path)))
    : h('div', { class: 'link-candidates' }, createButton(problem));
  return h('li', { class: 'link-problem is-' + problem.status },
    h('div', { class: 'link-problem-name' },
      textNode('code', problem.raw), textNode('span', label, 'link-badge is-' + problem.status),
      textNode('small', 'line ' + problem.line, 'muted')),
    actions);
}

function render() {
  if (typeof document === 'undefined') return; // a render queued before the page went away
  const host = $('linkStatus');
  const problems = state.current ? currentProblems(getText()) : [];
  host.hidden = !problems.length;
  $('linkStatusList').replaceChildren();
  $('linkStatusSummary').textContent = problems.length ? 'Links: ' + linkSummary(problems) : '';
  if (!problems.length) return;
  const list = $('linkStatusList');
  problems.slice(0, MAX_ROWS).forEach((problem) => list.appendChild(problemRow(problem)));
  if (problems.length > MAX_ROWS) {
    list.appendChild(h('li', { class: 'muted' }, 'and ' + (problems.length - MAX_ROWS) + ' more'));
  }
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(render, RENDER_DELAY_MS);
}

export function initLinkStatus() {
  on(Events.DRAFT_CHANGED, schedule);
  on(Events.ENTRY_OPENED, render);
  on(Events.ENTRY_OPENING, () => {
    $('linkStatus').hidden = true;
  });
  onMarksChanged(render);
}
