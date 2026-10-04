// The full word generator (the `/` page) in a drawer over the desk.
//
// The page is loaded once, lazily, as a same-origin iframe and then kept
// alive, so its draw history and pool choices survive closing and reopening.
// The desk behind the drawer is only made inert, never re-rendered, so an
// open draft stays exactly as it was.

import { $, h } from './dom.js';

export const EMBED_URL = '/?embed=1';
// Posted by the embedded generator (app.js) when Esc is pressed inside it.
export const CLOSE_MESSAGE = 'rw:generator-close';

// True for a query string that asks for the embedded page. Mirrors the
// inline script at the top of index.html, which has to run before paint.
export function isEmbedSearch(search) {
  const text = String(search || '').replace(/^\?/, '');
  return text.split('&').some((part) => part === 'embed=1');
}

export function sameWords(a, b) {
  return a.length === b.length && a.every((word, at) => word === b[at]);
}

// Esc closes an open drawer; nothing else does.
export function closesOnKey(event, isOpen) {
  return isOpen && event.key === 'Escape';
}

export function isCloseMessage(event, frameWindow, origin) {
  return Boolean(event && event.origin === origin && event.source === frameWindow
    && event.data && event.data.type === CLOSE_MESSAGE);
}

// `onClose` runs after the drawer hides; bench.js uses it to re-read kept words.
export function initGeneratorDrawer(options) {
  const onClose = (options && options.onClose) || (() => {});
  const drawer = $('generatorDrawer');
  const host = $('generatorFrameHost');
  const opener = $('openGenerator');
  let frame = null;
  let returnFocus = null;

  const isOpen = () => !drawer.hidden;

  // Everything else in the body goes inert while the sheet is up, so Tab and
  // clicks cannot reach the desk behind it. Nothing in it is re-rendered.
  function setBackgroundInert(inert) {
    Array.from(document.body.children).forEach((node) => {
      if (node === drawer || String(node.tagName).toLowerCase() === 'script') return;
      if (inert) node.setAttribute('inert', '');
      else node.removeAttribute('inert');
    });
  }

  function ensureFrame() {
    if (frame) return;
    frame = h('iframe', {
      class: 'generator-frame', src: EMBED_URL, title: 'Word generator', loading: 'lazy',
    });
    host.replaceChildren(frame);
  }

  function open() {
    if (isOpen()) return;
    ensureFrame();
    returnFocus = document.activeElement || opener;
    drawer.hidden = false;
    opener.setAttribute('aria-expanded', 'true');
    setBackgroundInert(true);
    $('closeGenerator').focus();
  }

  function close() {
    if (!isOpen()) return;
    drawer.hidden = true;
    opener.setAttribute('aria-expanded', 'false');
    setBackgroundInert(false);
    if (returnFocus && typeof returnFocus.focus === 'function') returnFocus.focus();
    returnFocus = null;
    onClose();
  }

  opener.addEventListener('click', () => (isOpen() ? close() : open()));
  $('closeGenerator').addEventListener('click', close);
  $('generatorScrim').addEventListener('click', close);
  document.addEventListener('keydown', (event) => {
    if (closesOnKey(event, isOpen())) {
      if (event.preventDefault) event.preventDefault();
      close();
    }
  });
  window.addEventListener('message', (event) => {
    if (isCloseMessage(event, frame && frame.contentWindow, location.origin)) close();
  });

  return { open, close, isOpen, frame: () => frame };
}
