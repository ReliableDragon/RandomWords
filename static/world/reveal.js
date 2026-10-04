// Scrolling a span of the textarea into view. A textarea only scrolls to its
// caret when the user types, so a span selected by code (a staged link, a
// highlight from a report) can sit far below the visible part of the page.
//
// The span's height inside the textarea is measured with a hidden mirror that
// wraps the text the way the textarea does.

const MIRROR_STYLES = [
  'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing',
  'wordSpacing', 'textTransform', 'textIndent', 'tabSize', 'whiteSpace', 'overflowWrap',
  'wordBreak', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
];

// How far a scroller must move so [top, bottom] sits inside [viewTop, viewBottom],
// with the span a third of the way down when it had to move. 0 when visible.
export function revealDelta(top, bottom, viewTop, viewBottom, margin) {
  const room = margin || 0;
  if (top >= viewTop + room && bottom <= viewBottom - room) return 0;
  const height = viewBottom - viewTop;
  return top - (viewTop + Math.min(height / 3, height - (bottom - top) - room));
}

// The line box the offset falls in, in pixels from the top of the text.
function measureLine(field, offset) {
  const mirror = document.createElement('div');
  const computed = getComputedStyle(field);
  MIRROR_STYLES.forEach((name) => { mirror.style[name] = computed[name]; });
  Object.assign(mirror.style, {
    position: 'absolute', visibility: 'hidden', left: '-9999px', top: '0',
    boxSizing: 'border-box', border: '0', overflow: 'hidden',
    width: field.clientWidth + 'px',
  });
  mirror.appendChild(document.createTextNode(field.value.slice(0, offset)));
  const marker = document.createElement('span');
  marker.textContent = '​';
  mirror.appendChild(marker);
  document.body.appendChild(mirror);
  const top = marker.offsetTop;
  const lineHeight = parseFloat(computed.lineHeight) || marker.offsetHeight || 24;
  mirror.remove();
  return { top, bottom: top + lineHeight };
}

function scrollableParents(field) {
  const parents = [];
  for (let node = field.parentElement; node; node = node.parentElement) {
    const overflow = getComputedStyle(node).overflowY;
    if ((overflow === 'auto' || overflow === 'scroll') && node.scrollHeight > node.clientHeight) {
      parents.push(node);
    }
  }
  return parents;
}

// Scrolls the textarea, the panes around it and the page so the start of
// [start, end) is visible. Does nothing without layout (tests, hidden pane).
export function revealRange(field, start) {
  if (typeof getComputedStyle !== 'function' || !field.getBoundingClientRect) return;
  if (!field.clientWidth || !document.body || !document.createElement) return;
  const line = measureLine(field, start);
  const inside = revealDelta(line.top, line.bottom, field.scrollTop, field.scrollTop + field.clientHeight, 8);
  if (inside && field.scrollHeight > field.clientHeight) field.scrollTop += inside;
  const measure = () => {
    const box = field.getBoundingClientRect();
    return { top: box.top + line.top - field.scrollTop, bottom: box.top + line.bottom - field.scrollTop };
  };
  scrollableParents(field).forEach((parent) => {
    const at = measure();
    const view = parent.getBoundingClientRect();
    parent.scrollTop += revealDelta(at.top, at.bottom, view.top, view.bottom, 24);
  });
  const at = measure();
  const shift = revealDelta(at.top, at.bottom, 0, window.innerHeight, 24);
  if (shift && typeof window.scrollBy === 'function') window.scrollBy(0, shift);
}
