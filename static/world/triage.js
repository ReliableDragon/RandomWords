// Dismissing report rows ("Not a name", "Not drift", ...) and taking them back.
//
// A dismissal is a {kind, key} pair the server remembers; the `triage` object
// on a report row is exactly what to send. Kinds: name, drift, word, mention,
// target (never suggest links to this entry).

import { world } from './api.js';
import { button, h, textNode } from './dom.js';
import { entryTitle } from './text.js';

const UNDO_MS = 6000;

export function dismiss(triage) {
  return world.post('/triage', { action: 'dismiss', kind: triage.kind, key: triage.key });
}

export function restore(triage) {
  return world.post('/triage', { action: 'restore', kind: triage.kind, key: triage.key });
}

// Dismissals of the given kinds, newest first.
export async function listDismissals(kinds) {
  const data = await world.get('/triage');
  return filterDismissals(data.dismissals || [], kinds);
}

export function filterDismissals(dismissals, kinds) {
  return dismissals
    .filter((row) => kinds.indexOf(row.kind) >= 0)
    .sort((a, b) => String(b.dismissed_at || '').localeCompare(String(a.dismissed_at || '')));
}

// A readable line for a stored dismissal.
export function dismissalLabel(row) {
  if (row.kind === 'mention') {
    const parts = String(row.key).split('|');
    return entryTitle({ path: parts[0] }) + ' → ' + entryTitle({ path: parts[1] || '' })
      + ' (every mention in this note)';
  }
  if (row.kind === 'target') return 'Never suggest links to ' + entryTitle({ path: row.key });
  return String(row.key);
}

// Removes `node` from the page at once and puts a "Dismissed · Undo" strip in
// its place for a few seconds. If the server refuses, the row comes back with
// the reason. `onChange(delta)` reports -1 on dismiss and +1 on undo.
export async function dismissRow({ node, triage, label, onChange }) {
  const change = onChange || (() => {});
  const strip = h('div', { class: 'triage-undo', role: 'status' });
  node.after(strip);
  node.remove();
  strip.replaceChildren(textNode('span', 'Dismissing…', 'muted'));
  try {
    await dismiss(triage);
  } catch (error) {
    strip.after(node);
    strip.remove();
    node.appendChild(textNode('p', error.message, 'tree-error'));
    return false;
  }
  change(-1);
  let timer = null;
  const undo = button('Undo', 'text-button', async () => {
    clearTimeout(timer);
    undo.disabled = true;
    try {
      await restore(triage);
    } catch (error) {
      strip.replaceChildren(textNode('span', error.message, 'tree-error'));
      return;
    }
    strip.after(node);
    strip.remove();
    change(1);
  });
  strip.replaceChildren(textNode('span', (label || 'Dismissed') + ' · ', 'muted'), undo);
  timer = setTimeout(() => strip.remove(), UNDO_MS);
  return true;
}

// The label for a dismissal count and, when it differs, what they hide:
// "1 dismissed (hides 29 mentions)". `effect` is null when unknown.
export function dismissalText(count, effect, noun) {
  const base = count + ' dismissed';
  if (effect == null || !noun || effect === count) return base;
  return base + ' (hides ' + effect + ' ' + noun + (effect === 1 ? '' : 's') + ')';
}

// "N dismissed · Review": opens a list of what was dismissed, each with a
// Restore button. `count` is how many dismissals there are; `effect` (with
// `effectNoun`) how many rows they hide, when that is not the same thing.
// `bump(delta, effectDelta)` keeps both current as rows are dismissed (negative)
// or restored (positive) here. `onRestored` reloads the report.
export function dismissalSummary({ kinds, count, effect, effectNoun, onRestored }) {
  let shown = count || 0;
  let hides = effect == null ? null : effect;
  const label = h('span', { class: 'muted' });
  const list = h('div', { class: 'triage-review', hidden: true });
  const toggle = button('Review', 'text-button', () => {
    list.hidden = !list.hidden;
    toggle.setAttribute('aria-expanded', list.hidden ? 'false' : 'true');
    if (!list.hidden) fillReview();
  });
  toggle.setAttribute('aria-expanded', 'false');
  const element = h('div', { class: 'triage-summary' }, label, ' · ', toggle, list);

  function paint() {
    label.textContent = dismissalText(shown, hides, effectNoun);
    element.hidden = shown === 0 && list.hidden;
  }

  async function fillReview() {
    list.replaceChildren(textNode('p', 'Loading…', 'muted'));
    try {
      const rows = await listDismissals(kinds);
      list.replaceChildren(...(rows.length
        ? rows.map((row) => reviewRow(row))
        : [textNode('p', 'Nothing is dismissed here.', 'muted')]));
    } catch (error) {
      list.replaceChildren(textNode('p', error.message, 'tree-error'));
    }
  }

  function reviewRow(row) {
    const item = h('div', { class: 'triage-review-row' }, textNode('span', dismissalLabel(row)));
    item.appendChild(button('Restore', 'btn btn-small btn-quiet', async () => {
      try {
        await restore(row);
      } catch (error) {
        item.appendChild(textNode('small', error.message, 'tree-error'));
        return;
      }
      item.remove();
      shown = Math.max(0, shown - 1);
      hides = null; // unknown until the report reloads
      paint();
      if (onRestored) onRestored(row);
    }));
    return item;
  }

  paint();
  return {
    element,
    bump(delta, effectDelta = delta) {
      shown = Math.max(0, shown - delta);
      if (hides != null) hides = Math.max(0, hides - effectDelta);
      paint();
    },
  };
}
