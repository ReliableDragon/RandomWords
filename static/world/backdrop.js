// Underlines behind the textarea: unresolved or ambiguous wikilinks and the
// rarer spelling of known drift pairs.
//
// A mirror of the text sits under the (transparent) textarea with the same
// font, padding and wrapping, scrolled in step. Only the marks are visible,
// so the underlines land beneath the words they belong to. When the caret is
// inside a drift spelling, a small hint offers the safe replacement.

import { $, h } from './dom.js';
import { currentMarks, onMarksChanged } from './draft_marks.js';
import { driftAt, segments } from './editor_marks.js';
import { getText, replaceRange, showNotice, stageReplacement } from './editor.js';
import { Events, on } from './events.js';
import { state } from './state.js';

const MARK_CLASS = {
  drift: 'mark-drift',
  'link-unresolved': 'mark-unresolved',
  'link-ambiguous': 'mark-ambiguous',
};

let frame = 0;
let hinted = null;
// What the mirror shows now, so a scroll or resize does not rebuild it.
let drawn = null;

const field = () => $('entryText');

// One redraw per animation frame, however many events ask for it.
function schedule() {
  if (frame) return;
  const later = typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame : (fn) => setTimeout(fn, 16);
  frame = later(() => {
    frame = 0;
    draw();
  });
}

function fitToTextarea(backdrop, textarea) {
  // The mirror wraps at the textarea's text width, which shrinks when a
  // scrollbar appears, so size it to the client box rather than the border box.
  backdrop.style.width = textarea.clientWidth ? textarea.clientWidth + 'px' : '';
  backdrop.style.height = textarea.clientHeight ? textarea.clientHeight + 'px' : '';
  backdrop.scrollTop = textarea.scrollTop;
}

function markNode(piece) {
  if (!piece.mark) return document.createTextNode(piece.text);
  return h('mark', { class: MARK_CLASS[piece.mark.kind] || 'mark-drift', text: piece.text });
}

function paint(backdrop, text, marks) {
  if (!marks.length) {
    backdrop.replaceChildren();
    return;
  }
  const nodes = segments(text, marks).map(markNode);
  // A final newline needs something after it or the mirror is a line short.
  nodes.push(document.createTextNode('​'));
  backdrop.replaceChildren(...nodes);
}

function draw() {
  if (typeof document === 'undefined') return; // a redraw queued before the page went away
  const textarea = field();
  const backdrop = $('entryBackdrop');
  if (!textarea || !backdrop) return;
  const text = textarea.value;
  const marks = state.current || state.newDraft ? currentMarks(text) : [];
  if (!drawn || drawn.marks !== marks || drawn.text !== text || drawn.backdrop !== backdrop) {
    paint(backdrop, text, marks);
    drawn = { marks, text, backdrop };
  }
  fitToTextarea(backdrop, textarea);
  updateHint(marks);
}

// -- Drift hint ------------------------------------------------------------

function clearHint() {
  hinted = null;
  $('driftHint').hidden = true;
}

function updateHint(marks) {
  const textarea = field();
  const collapsed = textarea.selectionStart === textarea.selectionEnd;
  // Leave the hint alone while focus is elsewhere (on the hint's own button).
  if (document.activeElement !== undefined && document.activeElement !== textarea) return;
  const mark = collapsed && marks ? driftAt(marks, textarea.selectionStart) : null;
  if (!mark) {
    clearHint();
    return;
  }
  hinted = mark;
  $('driftHintText').textContent = mark.word + ' → ' + mark.replacement + '?';
  $('driftHint').hidden = false;
}

function refreshHint() {
  if (!state.current && !state.newDraft) return;
  updateHint(currentMarks(field().value));
}

// A new draft has no revision to check, only the text under the mark.
function replaceInDraft(mark) {
  if (getText().slice(mark.start, mark.end) !== mark.word) {
    showNotice('That word changed. Move the caret to it again.', true);
    return false;
  }
  replaceRange(mark.start, mark.end, mark.replacement, { select: true });
  showNotice('Spelling replaced (unsaved). Review the highlighted word, then save.');
  return true;
}

// Applies the offered replacement through the same safe path reports use:
// refused if the text under the range is no longer the word that was marked.
export function applyHint() {
  const mark = hinted;
  if (!mark || (!state.current && !state.newDraft)) return Promise.resolve(false);
  clearHint();
  if (!state.current) return Promise.resolve(replaceInDraft(mark));
  return stageReplacement(
    { path: state.current, revision: state.revision, start: mark.start, end: mark.end, expected: mark.word },
    mark.replacement,
    {
      stale: 'That word changed. Move the caret to it again.',
      staged: 'Spelling replaced (unsaved). Review the highlighted word, then save.',
    });
}

function onKeydown(event) {
  if (event.altKey && event.key === 'Enter' && hinted) {
    event.preventDefault();
    applyHint();
  }
}

export function initBackdrop() {
  const textarea = field();
  textarea.addEventListener('input', schedule);
  textarea.addEventListener('scroll', schedule);
  textarea.addEventListener('keydown', onKeydown);
  ['keyup', 'click', 'focus'].forEach((name) => textarea.addEventListener(name, refreshHint));
  textarea.addEventListener('blur', (event) => {
    const hint = $('driftHint');
    if (!(hint.contains && hint.contains(event.relatedTarget))) clearHint();
  });
  // A click on Replace must not move focus away from the caret's word.
  $('driftHintApply').addEventListener('mousedown', (event) => event.preventDefault());
  $('driftHintApply').addEventListener('click', applyHint);
  on(Events.DRAFT_CHANGED, schedule);
  on(Events.ENTRY_OPENED, schedule);
  onMarksChanged(schedule);
  window.addEventListener('resize', schedule);
  if (typeof ResizeObserver === 'function') new ResizeObserver(schedule).observe(textarea);
  if (document.fonts) {
    if (document.fonts.ready) document.fonts.ready.then(schedule);
    if (document.fonts.addEventListener) document.fonts.addEventListener('loadingdone', schedule);
  }
}
