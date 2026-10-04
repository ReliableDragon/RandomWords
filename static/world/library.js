// Readable names for word-library source texts such as
// "natural_history/marco_polo.txt". Nothing here touches the DOM.

const MAX_TEXTS = 4;

function titleCase(words) {
  return words.replace(/[_-]+/g, ' ').trim().replace(/\b([a-z])/g, (letter) => letter.toUpperCase());
}

// "natural_history/marco_polo.txt" -> "Marco Polo (natural history)".
export function libraryTitle(path) {
  const parts = String(path || '').split('/').filter(Boolean);
  if (!parts.length) return '';
  const name = titleCase(parts.pop().replace(/\.[A-Za-z0-9]+$/, ''));
  const topic = parts.length ? parts[parts.length - 1].replace(/[_-]+/g, ' ') : '';
  return topic ? name + ' (' + topic + ')' : name;
}

// A one-line summary of {count, texts}, or '' when no library text uses it.
export function whichSummary(which) {
  if (!which || !which.count) return '';
  const titles = (which.texts || []).slice(0, MAX_TEXTS).map(libraryTitle);
  const more = which.count - titles.length;
  const noun = which.count === 1 ? 'library text' : 'library texts';
  const list = titles.length ? ': ' + titles.join(', ') + (more > 0 ? ' and ' + more + ' more' : '') : '';
  return 'In ' + which.count + ' ' + noun + list;
}
