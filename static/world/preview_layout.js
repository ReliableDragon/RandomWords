// Pure decisions for the editor's preview: side by side or swapped in, and
// the note under the preview about markdown it could not render.

const SPLIT_MIN_VIEWPORT = 1100;
const SPLIT_MIN_EDITOR = 760;

// The editor and preview fit side by side only on a wide window whose editor
// column is itself wide (the sidebar and Nearby take their share).
export function splitFits(viewportWidth, editorWidth) {
  return viewportWidth >= SPLIT_MIN_VIEWPORT && editorWidth >= SPLIT_MIN_EDITOR;
}

export function previewLabel(canSplit, previewOn) {
  if (canSplit) return 'Split';
  return previewOn ? 'Edit' : 'Preview';
}

// Where a pane of scrollable height `targetMax` should sit so it stays roughly
// level with a pane that has scrolled `top` of its own `max`.
export function proportionalScroll(top, max, targetMax) {
  if (!(max > 0) || !(targetMax > 0)) return 0;
  return Math.round(Math.min(1, Math.max(0, top / max)) * targetMax);
}

const SKIPPED_LABELS = { table: 'tables', image: 'images', embed: 'embeds', task: 'task lists' };

// "Not rendered: tables, images", or '' when everything was rendered.
export function skippedText(kinds) {
  if (!Array.isArray(kinds) || !kinds.length) return '';
  return 'Not rendered: ' + kinds.map((kind) => SKIPPED_LABELS[kind] || String(kind)).join(', ');
}
