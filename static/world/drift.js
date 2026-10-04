// Spelling-drift occurrences, shown in both Upkeep and Lexicon.
//
// "Stage" puts the suggested spelling into the editor unsaved, so the writer
// reviews it before anything is written.

import { button, h, textNode } from './dom.js';
import { openEntry, stageReplacement } from './editor.js';
import { whichSummary } from './library.js';
import { dismissRow } from './triage.js';

const STAGE_MESSAGES = {
  stale: 'That occurrence changed. Refresh and try again.',
  staged: 'Correction staged. Review the highlighted word, then save.',
};

function stageCorrection(use, replacement) {
  return stageReplacement(
    { path: use.path, revision: use.revision, start: use.start, end: use.end, expected: use.spelling },
    replacement,
    STAGE_MESSAGES);
}

function occurrenceRow(use, replacement) {
  const stage = button('Stage ' + replacement, 'btn btn-small btn-primary', () => stageCorrection(use, replacement));
  stage.title = 'Stage this suggestion in the editor for review';
  return h('div', { class: 'drift-occurrence' },
    h('div', null,
      h('span', { class: 'drift-context' },
        use.context_before || '', textNode('mark', use.spelling, 'drift-token'), use.context_after || ''),
      textNode('small', use.path + ' · line ' + use.line, 'report-path')),
    h('div', { class: 'drift-actions' },
      button('Open', 'btn btn-small btn-quiet', () => openEntry(use.path)),
      stage));
}

// Adds one row per occurrence of `pair` (a drift pair or an Upkeep item).
export function appendDriftOccurrences(card, pair) {
  card.classList.add('drift-card');
  (pair.occurrences || []).forEach((use) => {
    card.appendChild(occurrenceRow(use, use.replacement || pair.to));
  });
}

function usesLine(word, count, which) {
  const library = whichSummary(which);
  const uses = count === 1 ? ' use' : ' uses';
  return textNode('small', word + ': ' + count + uses + (library ? ' · ' + library : ''), 'report-path');
}

// A whole drift pair as a card: what it suggests, how often each spelling
// occurs (and in library texts), its occurrences, and "Not drift".
// `onChange(delta)` hears about dismissals so counts can follow.
export function driftPairCard(pair, onChange) {
  const card = h('article', { class: 'report-card drift-card' },
    textNode('strong', 'Suggested: ' + pair.from + ' → ' + pair.to),
    textNode('small', 'Distance ' + pair.distance, 'report-path'),
    usesLine(pair.from, pair.from_count, pair.from_which),
    usesLine(pair.to, pair.to_count, pair.to_which));
  appendDriftOccurrences(card, pair);
  if (pair.triage) {
    card.appendChild(h('div', { class: 'drift-actions' },
      button('Not drift', 'btn btn-small btn-quiet', () => dismissRow({
        node: card, triage: pair.triage, label: 'Dismissed ' + pair.from + ' / ' + pair.to, onChange,
      }))));
  }
  return card;
}
