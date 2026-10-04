// Lexicon: coined words, where they are used, and possible spelling drift.

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { driftPairCard } from './drift.js';
import { openEntry } from './editor.js';
import { whichSummary } from './library.js';
import { createReportView } from './report.js';
import { dismissalSummary, dismissRow } from './triage.js';

const FILTER_DEBOUNCE_MS = 220;

// The query string for the current filter controls.
export function lexiconQuery(filters) {
  const query = {};
  if (filters.q) query.q = filters.q;
  if (filters.biome) query.biome = filters.biome;
  if (filters.once) query.once = '1';
  return query;
}

function readFilters() {
  return {
    q: $('lexiconQuery').value.trim(),
    biome: $('lexiconBiome').value,
    once: $('lexiconOnce').checked,
  };
}

// Rebuilds the biome menu from the response, keeping the current choice.
function fillBiomes(biomes) {
  const select = $('lexiconBiome');
  const selected = select.value;
  while (select.options.length > 1) select.remove(1);
  biomes.forEach((biome) => select.appendChild(new Option(biome.title || biome.path, biome.path)));
  if (biomes.some((biome) => biome.path === selected)) select.value = selected;
}

// The dismissal summary's numbers: what was dismissed and what that hides
// (a dismissed word also hides drift pairs). Older servers only send the second.
function dismissalNumbers(data, key) {
  const hidden = (data.dismissed || {})[key];
  const made = (data.dismissals || {})[key];
  return { count: made == null ? hidden : made, effect: made == null ? null : hidden };
}

function driftSection(drift, numbers) {
  const countNode = textNode('span', drift.length, 'report-count');
  const section = h('details', { class: 'report-section', dataset: { key: 'drift' } },
    h('summary', { class: 'report-section-heading' },
      textNode('h3', 'Possible spelling drift'), countNode));
  let count = drift.length;
  const summary = dismissalSummary({
    kinds: ['drift'], count: numbers.count, effect: numbers.effect, effectNoun: 'pair',
    onRestored: () => lexicon.load({ force: true }),
  });
  const onChange = (delta) => {
    count = Math.max(0, count + delta);
    countNode.textContent = count;
    summary.bump(delta);
  };
  section.appendChild(summary.element);
  drift.forEach((pair) => section.appendChild(driftPairCard(pair, onChange)));
  return section;
}

function useRow(use) {
  const biomes = (use.biomes || []).length ? ' · ' + use.biomes.join(', ') : '';
  return h('div', { class: 'lexicon-use' },
    button(use.path, 'report-entry-link', () => openEntry(use.path)),
    textNode('small', use.count + ' occurrences' + biomes, 'report-path'));
}

function wordCard(entry, onChange) {
  const card = h('article', { class: 'lexicon-entry report-card' },
    h('div', { class: 'report-section-heading' },
      textNode('h3', entry.word), textNode('span', entry.count + ' uses', 'report-count')),
    textNode('p', (entry.spellings || []).map((s) => s.spelling + ' (' + s.count + ')').join(' · '), 'lexicon-spellings'),
    h('div', { class: 'lexicon-uses' }, (entry.uses || []).map(useRow)));
  const library = whichSummary(entry.which);
  if (library) card.appendChild(textNode('small', library, 'lexicon-library-use'));
  if (entry.triage) {
    card.appendChild(h('div', { class: 'world-actions report-actions' },
      button('Real word', 'btn btn-small btn-quiet', () => dismissRow({
        node: card, triage: entry.triage, label: 'Dismissed “' + entry.word + '”', onChange,
      }))));
  }
  return card;
}

function renderLexicon(data) {
  fillBiomes(data.biomes || []);
  const dismissed = data.dismissed || {};
  const drift = data.drift || [];
  const entries = data.entries || [];
  const wordNumbers = dismissalNumbers(data, 'entries');
  const words = dismissalSummary({
    kinds: ['word'], count: wordNumbers.count, effect: wordNumbers.effect, effectNoun: 'word',
    onRestored: () => lexicon.load({ force: true }),
  });
  const fragment = document.createDocumentFragment();
  if (drift.length || dismissed.drift) {
    fragment.appendChild(driftSection(drift, dismissalNumbers(data, 'drift')));
  }
  fragment.appendChild(words.element);
  if (!entries.length) fragment.appendChild(textNode('p', 'No coined words match these filters.', 'muted'));
  entries.forEach((entry) => fragment.appendChild(wordCard(entry, words.bump)));
  $('lexiconContent').replaceChildren(fragment);
}

export const lexicon = createReportView({
  hostId: 'lexiconContent',
  loadingText: 'Loading lexicon…',
  getData: () => world.get('/lexicon', lexiconQuery(readFilters())),
  render: renderLexicon,
});

export const load = lexicon.load;

export function initLexicon() {
  let timer = null;
  const reload = () => lexicon.load({ force: true });
  $('lexiconQuery').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(reload, FILTER_DEBOUNCE_MS);
  });
  $('lexiconBiome').addEventListener('change', reload);
  $('lexiconOnce').addEventListener('change', reload);
}
