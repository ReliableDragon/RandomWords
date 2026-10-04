// The load-once-then-refresh behavior shared by the report views.

import { $, textNode } from './dom.js';

// Where the reader is inside a rendered report: scroll offsets of the page
// and of every scrolled ancestor or marked container, and which keyed
// <details> sections are open. Restored after a reload so it feels in place.
export function snapshotView(host) {
  const scrolls = [];
  for (let node = host; node; node = node.parentNode) {
    if (node.scrollTop || node.scrollLeft) scrolls.push({ node, top: node.scrollTop, left: node.scrollLeft });
  }
  if (typeof window !== 'undefined' && window.scrollY) {
    scrolls.push({ page: true, top: window.scrollY, left: 0 });
  }
  const open = {};
  if (host.querySelectorAll) {
    host.querySelectorAll('details').forEach((section) => {
      const key = section.dataset && section.dataset.key;
      if (key) open[key] = Boolean(section.open);
    });
    host.querySelectorAll('[data-scroll-key]').forEach((node) => {
      if (node.scrollTop || node.scrollLeft) {
        scrolls.push({ key: node.dataset.scrollKey, top: node.scrollTop, left: node.scrollLeft });
      }
    });
  }
  return { scrolls, open };
}

export function restoreView(host, snapshot) {
  if (host.querySelectorAll) {
    host.querySelectorAll('details').forEach((section) => {
      const key = section.dataset && section.dataset.key;
      if (key && key in snapshot.open) section.open = snapshot.open[key];
    });
  }
  snapshot.scrolls.forEach((saved) => {
    if (saved.page) {
      if (window.scrollTo) window.scrollTo(0, saved.top);
      return;
    }
    const node = saved.node || (host.querySelector
      && host.querySelector('[data-scroll-key="' + saved.key + '"]'));
    if (!node) return;
    node.scrollTop = saved.top;
    node.scrollLeft = saved.left;
  });
}

// `getData()` resolves to the data; `render(data)` fills the host element.
// The host's data-loaded attribute is 'loading', 'yes' or 'no'.
//
// A forced reload of an already-shown report keeps the old content (and the
// reader's place in it) until the new data arrives. `background: true` also
// keeps it if the reload fails, so a quiet refresh never wipes the screen.
export function createReportView(options) {
  let sequence = 0;
  let loadedGeneration = null;

  async function load(loadOptions) {
    const opts = loadOptions || {};
    const force = Boolean(opts.force);
    const host = $(options.hostId);
    if (!force && host.dataset.loaded === 'yes') return;
    const inPlace = force && host.dataset.loaded === 'yes';
    const mine = ++sequence;
    host.dataset.loaded = 'loading';
    if (inPlace) host.setAttribute('aria-busy', 'true');
    else host.replaceChildren(textNode('p', options.loadingText, 'muted'));
    try {
      const data = await options.getData();
      if (mine !== sequence) return;
      host.removeAttribute('aria-busy');
      // Taken after the wait, so scrolling during the fetch is not undone.
      const snapshot = inPlace ? snapshotView(host) : null;
      options.render(data);
      loadedGeneration = data && data.generation != null ? data.generation : null;
      host.dataset.loaded = 'yes';
      if (snapshot) restoreView(host, snapshot);
    } catch (error) {
      if (mine !== sequence) return;
      host.removeAttribute('aria-busy');
      host.dataset.loaded = 'no';
      if (!(inPlace && opts.background)) host.replaceChildren(textNode('p', error.message, 'tree-error'));
    }
  }

  function invalidate() {
    $(options.hostId).dataset.loaded = 'no';
    loadedGeneration = null;
  }

  // The index generation of the data on screen; null before the first load.
  function generation() {
    return loadedGeneration;
  }

  return { load, invalidate, generation };
}
