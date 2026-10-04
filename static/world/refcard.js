// The Reference card: a read-only peek at another entry beside the editor.

import { world } from './api.js';
import { $, button, h, textNode } from './dom.js';
import { openEntry } from './editor.js';
import { Events, on } from './events.js';
import { entryTitle, isPeoplePath, textareaText } from './text.js';

const MAX_SECTION_CHARS = 1800;

function headerLines(lines) {
  const header = [];
  let at = 0;
  if (lines[0] && lines[0].trim() === '---') {
    header.push(lines[0]);
    at = 1;
    while (at < lines.length) {
      header.push(lines[at]);
      at++;
      if (lines[at - 1].trim() === '---') break;
    }
  }
  while (at < lines.length && /^(From|Origin|Source|Themes):/i.test(lines[at])) {
    header.push(lines[at]);
    at++;
  }
  return { header, at };
}

function firstParagraph(lines, from) {
  let at = from;
  while (at < lines.length && !lines[at].trim()) at++;
  const paragraph = [];
  while (at < lines.length && lines[at].trim()) {
    paragraph.push(lines[at]);
    at++;
  }
  return { paragraph, at };
}

function factsSection(lines, from) {
  const facts = [];
  let inFacts = false;
  for (let i = from; i < lines.length; i++) {
    if (/^##\s+Facts\s*$/i.test(lines[i])) {
      inFacts = true;
      facts.push(lines[i]);
    } else if (inFacts && /^##\s+/.test(lines[i])) {
      break;
    } else if (inFacts) {
      facts.push(lines[i]);
    }
  }
  return facts;
}

// A quote is a block-quote whose last line ends in "- [[Speaker]]".
function attributedQuotes(lines) {
  const quotes = [];
  lines.forEach((line, i) => {
    if (!/(?:^|\s)-\s*\[\[[^\]]+\]\]\s*$/.test(line)) return;
    let begin = i;
    while (begin > 0 && /^\s*>/.test(lines[begin - 1])) begin--;
    quotes.push(lines.slice(begin, i + 1).join('\n'));
  });
  return quotes;
}

// Splits raw entry text into the parts the card shows.
export function parseReference(raw) {
  const lines = textareaText(raw || '').split('\n');
  const { header, at } = headerLines(lines);
  const first = firstParagraph(lines, at);
  return {
    header: header.join('\n'),
    first: first.paragraph.join('\n'),
    facts: factsSection(lines, first.at).join('\n'),
    quotes: attributedQuotes(lines).join('\n\n'),
  };
}

function referenceSection(label, value) {
  const text = (value || '').trim();
  if (!text) return null;
  return h('section', { class: 'reference-section' },
    textNode('strong', label), textNode('p', text.slice(0, MAX_SECTION_CHARS)));
}

// Fills `host` with the attributed quotes for one character.
export async function loadVoiceQuotes(host, path) {
  host.replaceChildren(textNode('p', 'Loading voice…', 'muted'));
  try {
    const data = await world.get('/quotes', { by: path });
    host.replaceChildren();
    const quotes = data.quotes || [];
    if (!quotes.length) host.appendChild(textNode('p', 'No attributed quotes yet.', 'muted'));
    quotes.forEach((quote) => {
      const block = h('blockquote', null, quote.text || '');
      if (quote.path) {
        block.appendChild(button(quote.title || entryTitle(quote), 'report-entry-link', () => openEntry(quote.path)));
      }
      host.appendChild(block);
    });
  } catch (error) {
    host.replaceChildren(textNode('p', error.message, 'tree-error'));
  }
}

function voiceSection(path) {
  const body = h('div');
  loadVoiceQuotes(body, path);
  return h('section', { class: 'reference-section reference-voice' }, textNode('strong', 'Voice'), body);
}

export function hideReference() {
  $('referenceCard').hidden = true;
}

export async function openReference(path) {
  if (!path) return;
  try {
    const data = await world.get('/entry', { path });
    $('referenceTitle').textContent = (data.entry && data.entry.title) || entryTitle({ path });
    $('referencePath').textContent = path;
    const parts = parseReference(data.text);
    const body = $('referenceBody');
    body.textContent = '';
    [
      referenceSection('Header', parts.header),
      referenceSection('First paragraph', parts.first),
      referenceSection('Facts', parts.facts),
      referenceSection('Attributed quotes', parts.quotes),
      isPeoplePath(path) ? voiceSection(path) : null,
    ].forEach((section) => { if (section) body.appendChild(section); });
    $('referenceCard').hidden = false;
  } catch (error) {
    $('nearbyState').textContent = error.message;
  }
}

export function initRefcard() {
  $('closeReference').addEventListener('click', hideReference);
  on(Events.ENTRY_OPENING, hideReference);
  on(Events.REFERENCE_REQUESTED, (detail) => openReference(detail && detail.path));
}
