// What the editor knows about problems in the open entry: the server's link
// statuses for the saved text, and the vault's known spelling drift.
//
// This module owns the data and tells listeners when it changes. It never
// touches the page; backdrop.js and link_status.js draw it.

import { world } from './api.js';
import { buildMarks, driftIndex, linkKey, linkStatusMap, problemLinks } from './editor_marks.js';

const DRIFT_MAX_AGE_MS = 60000;
const DRIFT_RETRY_MS = 30000;

let linkMap = new Map();
let linkGeneration = null;
let fromTargets = [];
let drift = new Map();
let driftGeneration = null;
let driftLoadedAt = 0;
let driftFailedAt = 0;
let driftLoading = null;
// The generation the last lexicon fetch was made for, and one noted while a
// fetch was in flight.
let driftAskedFor = null;
let driftWanted = null;
const listeners = new Set();

function changed() {
  Array.from(listeners).forEach((listener) => {
    try {
      listener();
    } catch (error) {
      console.error('draft marks listener failed', error);
    }
  });
}

// Calls listener whenever links or drift change. Returns an unsubscribe.
export function onMarksChanged(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Marks and link problems are asked for on every keyup, animation frame and
// panel render, so the last answer is kept while the text, link statuses and
// drift spellings are the same objects.
let marksCache = null;
let problemsCache = null;

export function currentMarks(text) {
  const c = marksCache;
  if (c && c.text === text && c.linkMap === linkMap && c.drift === drift) return c.marks;
  const marks = buildMarks(text, linkMap, drift);
  marksCache = { text, linkMap, drift, marks };
  return marks;
}

export function currentProblems(text) {
  const c = problemsCache;
  if (c && c.text === text && c.linkMap === linkMap) return c.problems;
  const problems = problemLinks(text, linkMap);
  problemsCache = { text, linkMap, problems };
  return problems;
}

export function getLinkMap() {
  return linkMap;
}

export function linksGeneration() {
  return linkGeneration;
}

// The From targets, as canonical paths, that resolved in the saved text.
export function fromTargetPaths() {
  const paths = [];
  fromTargets.forEach((item) => {
    const info = linkMap.get(linkKey(item.target || item));
    const path = info && info.status === 'resolved' ? info.resolved_path : null;
    if (path && paths.indexOf(path) < 0) paths.push(path);
  });
  return paths;
}

// Remembers which entries the draft's From: header names (Nearby reports
// them for unsaved text too).
export function setFromTargets(list) {
  fromTargets = Array.isArray(list) ? list : [];
}

// links: the entry route's link rows for the saved text.
export function setEntryLinks(links, generation, entry) {
  linkMap = linkStatusMap(links);
  linkGeneration = generation == null ? null : String(generation);
  if (entry && Array.isArray(entry.from_targets)) fromTargets = entry.from_targets;
  changed();
}

export function clearEntryLinks() {
  linkMap = new Map();
  linkGeneration = null;
  fromTargets = [];
  changed();
}

async function loadDrift(generation) {
  if (driftLoading) {
    // A newer generation noted mid-fetch is fetched once this one lands.
    driftWanted = generation == null ? driftWanted : String(generation);
    return driftLoading;
  }
  driftAskedFor = generation == null ? null : String(generation);
  driftLoading = (async () => {
    try {
      const data = await world.get('/lexicon');
      drift = driftIndex(data.drift);
      driftGeneration = String(data.generation == null ? generation : data.generation);
      driftLoadedAt = Date.now();
      changed();
    } catch (_) {
      driftFailedAt = Date.now();
    } finally {
      driftLoading = null;
    }
    const wanted = driftWanted;
    driftWanted = null;
    if (wanted !== null && wanted !== driftAskedFor && wanted !== driftGeneration) await loadDrift(wanted);
  })();
  return driftLoading;
}

// Fetches drift the first time, and again when the vault's generation moved
// on. `force` also refreshes a stale copy (a dismissal does not move it).
// A generation already fetched for, or already reported by the lexicon, is
// not fetched again.
export function noteGeneration(generation, force) {
  const known = driftGeneration !== null;
  const text = generation == null ? null : String(generation);
  const moved = text !== null && text !== driftGeneration && text !== driftAskedFor;
  const stale = force && Date.now() - driftLoadedAt > DRIFT_MAX_AGE_MS;
  if (known && !moved && !stale) return Promise.resolve();
  if (Date.now() - driftFailedAt < DRIFT_RETRY_MS && !known) return Promise.resolve();
  return loadDrift(generation);
}

export function resetForTests() {
  linkMap = new Map();
  linkGeneration = null;
  fromTargets = [];
  drift = new Map();
  driftGeneration = null;
  driftLoadedAt = 0;
  driftFailedAt = 0;
  driftLoading = null;
  driftAskedFor = null;
  driftWanted = null;
  marksCache = null;
  problemsCache = null;
}
