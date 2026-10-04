// Keeping your place across views: the "← Back to …" chip.
//
// When something inside a view (a Coverage ＋, an Upkeep row, an Atlas entry)
// sends the writer to the desk, the desk offers a way back to that view. The
// chip belongs to one trip: it goes when the writer picks the Desk tab
// themselves, moves on to another view, or uses it.

export const VIEW_LABELS = {
  desk: 'Desk',
  story: 'Story',
  map: 'Map',
  coverage: 'Coverage',
  upkeep: 'Upkeep',
  lexicon: 'Lexicon',
  backlog: 'Backlog',
};

// The view the desk's chip should return to after a switch, or null.
//   from, to  view names; `current` is the chip's target before the switch
//   via       'tab' when the writer clicked a view tab (or the chip itself)
export function nextReturnTo({ from, to, via, current }) {
  if (to !== 'desk') return null;
  if (from === 'desk') return current || null;
  if (via === 'tab') return null;
  return from && VIEW_LABELS[from] ? from : null;
}

export function returnLabel(view) {
  return '← Back to ' + (VIEW_LABELS[view] || view);
}

// Whether a visit to `to` should put the view back where it was left. A
// desk visit that something else asked for is about a different entry, so it
// starts at the top; coming back by tab or chip resumes.
export function resumesPlace({ from, to, via }) {
  if (from === to) return false;
  return to !== 'desk' || via === 'tab';
}
