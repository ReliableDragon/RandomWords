// Coverage: how many entries each biome has of each kind, shaded as a heatmap.

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { openCreate } from './create.js';
import { openEntry } from './editor.js';
import { createReportView } from './report.js';
import { entryTitle } from './text.js';

const HEAT_LEVELS = 4;

// 0 for an empty cell, else 1..4 by how full the cell is compared with the
// fullest one. Square-root scaling keeps small counts visible next to a few
// very large ones.
export function heatLevel(count, max) {
  if (!count || count < 1 || !max) return 0;
  return Math.min(HEAT_LEVELS, Math.max(1, Math.ceil(Math.sqrt(count / max) * HEAT_LEVELS)));
}

export function maxCount(rows, kinds) {
  let max = 0;
  rows.forEach((row) => kinds.forEach((kind) => {
    const cell = (row.cells && row.cells[kind]) || {};
    max = Math.max(max, cell.count || 0);
  }));
  return max;
}

// The create-form prefill for a cell's "Start entry here", or null when the
// server did not describe one.
export function cellCreatePrefill(cell) {
  const create = cell && cell.create;
  if (!create || !create.folder) return null;
  const prefill = { folder: create.folder, fromTargets: create.from_target ? [create.from_target] : [] };
  if (create.template) prefill.template = create.template;
  return prefill;
}

function openLink(label, path) {
  return button(label, 'report-entry-link', () => openEntry(path));
}

function membershipNote(member) {
  const via = typeof member === 'string' ? member : (member.via || 'membership');
  const source = typeof member === 'string' ? '' : (member.source_path || '');
  return textNode('small', via + (source ? ' · ' + source : ''), 'report-provenance');
}

function entryItem(entry) {
  const item = h('div', { class: 'coverage-entry' }, openLink(entry.title || entryTitle(entry), entry.path));
  (entry.memberships || []).forEach((member) => item.appendChild(membershipNote(member)));
  (entry.direct_places || []).forEach((place) => {
    item.appendChild(openLink('Direct place: ' + (place.title || entryTitle(place)), place.path));
  });
  return item;
}

function startButton(cell, kind, biome, className) {
  const prefill = cellCreatePrefill(cell);
  if (!prefill) return null;
  const label = 'Start a ' + kind + ' entry in ' + biome;
  const start = button('＋', className || 'coverage-add', () => openCreate(prefill));
  start.title = 'Start entry here';
  start.setAttribute('aria-label', label);
  return start;
}

// The panel under the table that lists a cell's entries.
function showCell(panel, row, kind, cell) {
  const biome = row.title || entryTitle(row);
  const entries = cell.entries || [];
  const start = startButton(cell, kind, biome, 'btn btn-small btn-primary');
  if (start) {
    start.textContent = 'Start entry here';
    start.classList.remove('coverage-add');
  }
  panel.replaceChildren(
    h('div', { class: 'coverage-panel-head' },
      textNode('h3', kind + ' in ' + biome), start),
    entries.length
      ? h('div', { class: 'coverage-panel-list' }, entries.map(entryItem))
      : textNode('p', 'No ' + kind + ' entries here yet.', 'muted'));
  panel.hidden = false;
  if (panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest' });
}

function countCell(row, kind, max, panel) {
  const cell = (row.cells && row.cells[kind]) || { count: 0, entries: [] };
  const total = cell.count == null ? (cell.entries || []).length : cell.count;
  const level = heatLevel(total, max);
  const count = button(String(total), 'coverage-count', () => {
    if (panel.selected) panel.selected.setAttribute('aria-expanded', 'false');
    panel.selected = count;
    count.setAttribute('aria-expanded', 'true');
    showCell(panel, row, kind, cell);
  });
  count.setAttribute('aria-expanded', 'false');
  count.setAttribute('aria-label', total + ' ' + kind + ' entries in ' + (row.title || row.path));
  return h('td', { class: 'heat-' + level + (total ? '' : ' is-thin') },
    h('div', { class: 'coverage-cell' }, count, startButton(cell, kind, row.title || entryTitle(row))));
}

function biomeRow(row, kinds, max, panel) {
  const name = h('th', { scope: 'row' },
    openLink(row.title || entryTitle(row), row.path), textNode('small', row.path, 'report-path'));
  return h('tr', null, name, kinds.map((kind) => countCell(row, kind, max, panel)));
}

function renderCoverage(data) {
  const host = $('coverageContent');
  const kinds = Array.isArray(data.kinds) ? data.kinds : [];
  const rows = Array.isArray(data.rows) ? data.rows : [];
  if (!rows.length) {
    host.replaceChildren(textNode('p', 'No canonical biome rows were found.', 'muted'));
    return;
  }
  const max = maxCount(rows, kinds);
  const panel = h('section', { class: 'coverage-panel', hidden: true, 'aria-live': 'polite' });
  const table = h('table', { class: 'coverage-table' },
    h('thead', null, h('tr', null, textNode('th', 'Biome'), kinds.map((kind) => textNode('th', kind)))),
    h('tbody', null, rows.map((row) => biomeRow(row, kinds, max, panel))));
  host.replaceChildren(
    h('div', { class: 'coverage-table-wrap', dataset: { scrollKey: 'coverage' } }, table),
    panel);
}

export const coverage = createReportView({
  hostId: 'coverageContent',
  loadingText: 'Loading coverage…',
  getData: () => world.get('/matrix'),
  render: renderCoverage,
});

export const load = coverage.load;
