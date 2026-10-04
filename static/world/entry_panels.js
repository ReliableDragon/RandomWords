// Read-only panels around the editor: frontmatter notes, entry details and
// backlinks. They render what they are given; opening entries is injected.

import { $, h, textNode } from './dom.js';
import { diagnosticText, entryTitle, pathFromResult } from './text.js';

export function renderEntryDiagnostics(items) {
  const host = $('entryDiagnostics');
  host.replaceChildren();
  const list = Array.isArray(items) ? items : [];
  host.hidden = !list.length;
  if (!list.length) return;
  host.appendChild(textNode('strong', 'Frontmatter notes'));
  host.appendChild(h('ul', null, list.map((item) => textNode('li', diagnosticText(item)))));
}

function originText(entry) {
  return (entry.origin || []).map((word) => {
    const gloss = entry.glosses && entry.glosses[word];
    return word + (gloss ? ' (' + gloss + ')' : '');
  }).join(' · ');
}

function metadataRows(entry) {
  return [
    ['From', (entry.from_targets || []).map((link) => link.display || link.target).join(' · ')],
    ['Origin', originText(entry)],
    ['Tags', (entry.tags || []).map((tag) => '#' + tag).join(' ')],
    ['Themes', (entry.themes || []).join(' · ')],
    ['Aliases', (entry.aliases || []).join(' · ')],
    ['Notes', (entry.notes || []).join(' · ')],
  ];
}

export function renderMetadataSummary(entry) {
  const host = $('metadataContent');
  if (!host) return;
  host.replaceChildren();
  metadataRows(entry || {}).forEach(([label, value]) => {
    if (!value) return;
    host.appendChild(h('div', { class: 'metadata-row' },
      textNode('strong', label), textNode('span', value)));
  });
  if (!host.childNodes.length) {
    host.appendChild(textNode('p', 'No supported structured fields found.', 'muted'));
  }
}

export function renderBacklinks(items, onOpen) {
  const host = $('backlinkList');
  const list = items || [];
  $('backlinkCount').textContent = list.length ? '(' + list.length + ')' : '';
  host.replaceChildren();
  if (!list.length) {
    host.appendChild(textNode('p', 'Nothing links here yet.', 'muted'));
    return;
  }
  list.forEach((item) => {
    const row = h('button', { type: 'button', class: 'backlink-item', onclick: () => onOpen(pathFromResult(item)) },
      textNode('strong', item.title || entryTitle(item)),
      textNode('p', item.context || item.sentence || item.text || item.path || ''));
    host.appendChild(row);
  });
}
