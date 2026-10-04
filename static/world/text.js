// Pure text and path helpers. Nothing here touches the DOM.

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escapeHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

// Textareas normalize every line ending to \n.
export function textareaText(value) {
  return String(value == null ? '' : value).replace(/\r\n?/g, '\n');
}

export function detectLineEnding(value) {
  const text = String(value || '');
  if (text.indexOf('\r\n') >= 0) return '\r\n';
  return text.indexOf('\r') >= 0 ? '\r' : '\n';
}

// The editor text as it should be written to disk.
export function toDiskText(value, lineEnding) {
  const text = textareaText(value);
  return lineEnding === '\n' ? text : text.replace(/\n/g, lineEnding);
}

export function displayPath(path) {
  return path.replace(/\.md$/i, '');
}

export function entryTitle(entry) {
  return entry.title || entry.name || (entry.path || '').split('/').pop().replace(/\.md$/i, '');
}

export function pathFromResult(result) {
  return result.path || result.entry_path || '';
}

export function folderParent(path) {
  const parts = (path || '').split('/').filter(Boolean);
  parts.pop();
  return parts.join('/');
}

// The openCreate prefill for an unresolved link target: [[Places/Harbor]]
// starts "Harbor" in Places (the folder is dropped by openCreate if the vault
// has none), a bare name starts in the vault root. A title never holds a "/".
export function createFromTarget(target, extra) {
  const parts = String(target || '').split('/').map((part) => part.trim()).filter(Boolean);
  const title = (parts.pop() || '').replace(/\.md$/i, '');
  const prefill = Object.assign({ title }, extra);
  if (parts.length) prefill.folder = parts.join('/');
  return prefill;
}

export function isPeoplePath(path) {
  return typeof path === 'string' && path.indexOf('People/') === 0;
}

// Splits "rainseed (a rain-made lantern), loam" on commas outside brackets.
export function splitSeeds(value) {
  return value
    .split(/,(?=(?:[^()]|\([^)]*\))*$)/)
    .map((seed) => seed.trim())
    .filter(Boolean);
}

// Report items may be plain strings or objects carrying a message.
export function diagnosticText(item) {
  return typeof item === 'string' ? item : (item.message || item.diagnostic || String(item));
}

// A download name that is safe on every platform, always ending in .html.
export function exportFilename(name, fallback) {
  let safe = String(name || fallback || 'story')
    .replace(/[^A-Za-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'story';
  if (!/\.html?$/i.test(safe)) safe += '.html';
  return safe;
}

// The title used to seed a new entry from a backlog idea.
export function ideaSeedTitle(expected) {
  return (expected || '').trim().split(/\s+/).slice(0, 4).join(' ').replace(/[.,;:!?]+$/, '');
}

function parseUrl(text, baseHref) {
  try {
    return new URL(text, baseHref);
  } catch (_) {
    return null;
  }
}

// Recognizes links in rendered previews that point at another entry:
// world:<path>, or the entry route on this page's own origin or the API.
// Returns null for other links (including the same route on another site),
// else {path} (path is empty when the link names none).
export function entryLinkTarget(href, worldApiBase, baseHref) {
  const text = href || '';
  if (text.indexOf('world:') === 0) return { path: decodeURIComponent(text.slice(6)) };
  const url = parseUrl(text, baseHref);
  if (!url) return null;
  const routes = ['/world/entry', worldApiBase + '/entry', '/api/world/entry'];
  const internal = routes.some((route) => {
    const at = parseUrl(route, baseHref);
    return at && at.origin === url.origin && at.pathname === url.pathname;
  });
  return internal ? { path: url.searchParams.get('path') || '' } : null;
}

// A browser draft written against an older revision than the one on disk is
// still the writer's work, but saving it as if it were based on the disk
// text would silently drop the outside edit. Returns the revision the draft
// should be saved against and whether it is out of date.
export function draftBase(draft, diskRevision) {
  const written = draft && draft.revision;
  if (!written || written === diskRevision) return { revision: diskRevision, stale: false };
  return { revision: written, stale: true };
}
