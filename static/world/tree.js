// The folder tree in the sidebar, and the New folder dialog.
//
// The tree is loaded on demand. Paths, rather than titles, remain the
// identity so duplicate titles in different folders stay distinct.

import { world } from './api.js';
import { $, h, setStatus } from './dom.js';
import { emit, Events, on } from './events.js';
import { openEntry } from './editor.js';
import { state } from './state.js';
import { entryTitle } from './text.js';

const expanded = new Set();
// Where each shown folder's rows live ('' is the root) and every row by path.
// Entries can outlive their DOM, so both are checked with isShown().
const hosts = new Map();
const rows = new Map();
let followSeq = 0;

function loadingNote() {
  return h('p', { class: 'tree-loading' }, 'Loading…');
}

function treeError(message, hint) {
  return h('p', { class: 'tree-error' }, message, hint && [h('br'), h('small', null, hint)]);
}

function rowLabel(item, isDir) {
  if (isDir) return item.name;
  return entryTitle(item);
}

function countLabel(item) {
  if (item.stub) return 'stub';
  return item.words == null ? '' : item.words;
}

const parentOf = (path) => path.split('/').slice(0, -1).join('/');

function isShown(node) {
  const root = $('worldTree');
  for (let at = node; at; at = at.parentNode) if (at === root) return true;
  return false;
}

function setCurrent(row, on) {
  row.classList.toggle('is-selected', on);
  if (on) row.setAttribute('aria-current', 'true');
  else row.removeAttribute('aria-current');
}

function treeRow(parentPath, item) {
  const path = item.path || ((parentPath ? parentPath + '/' : '') + item.name);
  const isDir = Boolean(item.is_dir);
  const marker = isDir ? (expanded.has(path) ? '▾' : '▸') : '·';
  const row = h('button', { type: 'button', class: 'tree-row', 'data-path': path },
    h('span', { class: 'tree-toggle' }, marker),
    h('span', { class: 'tree-name' }, rowLabel(item, isDir)),
    isDir ? null : h('span', { class: 'tree-count' }, countLabel(item)));
  if (isDir) row.setAttribute('aria-expanded', expanded.has(path) ? 'true' : 'false');
  else if (state.current === path) setCurrent(row, true);
  row.style.paddingLeft = (0.8 + (parentPath ? parentPath.split('/').length * 0.58 : 0)) + 'rem';
  row.addEventListener('click', () => {
    if (isDir) toggleFolder(path, row);
    else openEntry(path);
  });
  rows.set(path, row);
  return { row, path, isDir };
}

// Nested hosts below this folder are rebuilt (and re-registered) with it.
function forgetBelow(parentPath) {
  const prefix = parentPath + '/';
  Array.from(hosts.keys()).forEach((key) => {
    if (key !== parentPath && (!parentPath || key.indexOf(prefix) === 0)) hosts.delete(key);
  });
}

// Resolves when this folder and every open folder inside it are drawn.
export function renderTree(parentPath, entries, host) {
  forgetBelow(parentPath);
  hosts.set(parentPath, host);
  host.replaceChildren();
  const loads = [];
  (entries || []).forEach((item) => {
    const { row, path, isDir } = treeRow(parentPath, item);
    host.appendChild(row);
    if (!isDir || !expanded.has(path)) return;
    const children = h('div', { class: 'tree-children' }, loadingNote());
    host.appendChild(children);
    loads.push(item.entries ? renderTree(path, item.entries, children) : loadFolder(path, children));
  });
  return Promise.all(loads);
}

async function loadFolder(path, host) {
  try {
    const data = await world.get('/tree', { path });
    await renderTree(path, data.entries || [], host);
  } catch (error) {
    host.replaceChildren(treeError(error.message));
  }
}

function markFolder(row, open) {
  row.querySelector('.tree-toggle').textContent = open ? '▾' : '▸';
  row.setAttribute('aria-expanded', open ? 'true' : 'false');
}

async function openFolder(path, row) {
  expanded.add(path);
  markFolder(row, true);
  let child = row.nextElementSibling;
  if (!child || !child.classList.contains('tree-children')) {
    child = h('div', { class: 'tree-children' }, loadingNote());
    row.after(child);
  }
  // Always refetch: a folder may have gained entries since it was last open.
  await loadFolder(path, child);
}

async function toggleFolder(path, row) {
  if (expanded.has(path)) {
    expanded.delete(path);
    forgetBelow(path);
    hosts.delete(path);
    const child = row.nextElementSibling;
    if (child && child.classList.contains('tree-children')) child.remove();
    markFolder(row, false);
    return;
  }
  await openFolder(path, row);
}

export async function loadRoot() {
  const host = $('worldTree');
  try {
    const data = await world.get('/tree');
    state.vaultId = data.vault_id || state.vaultId;
    await renderTree('', data.entries || [], host);
    setStatus('Vault connected', 'ready');
  } catch (error) {
    host.replaceChildren(treeError(error.message, 'Start the server with a configured vault.'));
    setStatus('Vault unavailable', 'error');
  }
}

// -- Following the open entry ------------------------------------------------

function scrollToRow(row) {
  const box = row.closest && row.closest('.world-sidebar');
  if (!box || !box.clientHeight) return;
  // Scroll the sidebar itself: scrollIntoView could also move the whole page.
  const top = row.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
  if (top < box.scrollTop || top + row.offsetHeight > box.scrollTop + box.clientHeight) {
    box.scrollTop = Math.max(0, top - box.clientHeight / 3);
  }
}

function markCurrent(path) {
  Array.from($('worldTree').querySelectorAll('.tree-row.is-selected')).forEach((row) => setCurrent(row, false));
  const row = rows.get(path);
  if (!row || !isShown(row)) return;
  setCurrent(row, true);
  scrollToRow(row);
}

// Opens each closed ancestor folder in turn; false when a folder is not listed.
async function revealAncestors(path) {
  let folder = '';
  for (const part of parentOf(path).split('/').filter(Boolean)) {
    folder = folder ? folder + '/' + part : part;
    const host = hosts.get(folder);
    if (host && isShown(host)) continue;
    const row = rows.get(folder);
    if (!row || !isShown(row)) return false;
    await openFolder(folder, row);
  }
  return true;
}

async function followEntry(detail) {
  const path = detail && detail.path;
  if (!path) return;
  const mine = ++followSeq;
  if (!(await revealAncestors(path))) {
    // The listing is stale (a new folder, say): redraw from the root with the ancestors open.
    let folder = '';
    parentOf(path).split('/').filter(Boolean).forEach((part) => {
      folder = folder ? folder + '/' + part : part;
      expanded.add(folder);
    });
    await loadRoot();
  }
  if (mine !== followSeq) return;
  markCurrent(path);
  refreshFolder(parentOf(path));
}

// -- Refreshing one folder's badges ------------------------------------------

function rowPaths(host) {
  return Array.from(host.children).filter((node) => node.classList.contains('tree-row'))
    .map((node) => node.getAttribute('data-path'));
}

function listedPath(parentPath, item) {
  return item.path || ((parentPath ? parentPath + '/' : '') + item.name);
}

// Updates counts in place when the folder holds the same entries; otherwise redraws it.
export async function refreshFolder(path) {
  const host = hosts.get(path);
  if (!host || !isShown(host)) return;
  let entries;
  try {
    entries = (await world.get('/tree', path ? { path } : undefined)).entries || [];
  } catch (_) {
    return;
  }
  if (hosts.get(path) !== host || !isShown(host)) return;
  const listed = entries.map((item) => listedPath(path, item));
  const shown = rowPaths(host);
  if (listed.length !== shown.length || listed.some((p, i) => p !== shown[i])) {
    await renderTree(path, entries, host);
    return;
  }
  entries.forEach((item) => {
    const badge = !item.is_dir && rows.get(listedPath(path, item)).querySelector('.tree-count');
    if (badge) badge.textContent = countLabel(item);
  });
}

// Every folder and file path in the vault, found breadth first. The tree
// route lists one folder at a time, so this is one request per folder.
export async function walkVault() {
  const folders = [];
  const files = [];
  const queue = [''];
  while (queue.length) {
    const parent = queue.shift();
    const data = await world.get('/tree', parent ? { path: parent } : undefined);
    if (!parent) state.vaultId = data.vault_id || state.vaultId;
    (data.entries || []).forEach((item) => {
      const path = item.path || (parent ? parent + '/' : '') + item.name;
      if (item.is_dir) {
        folders.push(path);
        queue.push(path);
      } else {
        files.push(path);
      }
    });
  }
  return { folders: Array.from(new Set(folders)), files: Array.from(new Set(files)) };
}

async function openNewFolderDialog() {
  const dialog = $('newFolderDialog');
  const parent = $('newFolderParent');
  const error = $('newFolderError');
  $('newFolderForm').reset();
  error.hidden = true;
  parent.replaceChildren(new Option('Vault root', ''));
  try {
    const { folders } = await walkVault();
    folders.sort((a, b) => a.localeCompare(b));
    folders.forEach((path) => parent.appendChild(new Option(path, path)));
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', '');
  $('newFolderName').focus();
}

function closeNewFolderDialog() {
  const dialog = $('newFolderDialog');
  if (typeof dialog.close === 'function') dialog.close();
  else dialog.removeAttribute('open');
}

async function submitNewFolder(event) {
  event.preventDefault();
  const name = $('newFolderName').value.trim();
  const parent = $('newFolderParent').value;
  const error = $('newFolderError');
  const submit = $('newFolderSubmit');
  error.hidden = true;
  submit.disabled = true;
  try {
    const data = await world.post('/folder', { parent, name });
    await loadRoot();
    emit(Events.FOLDER_CREATED, { path: data.path || name });
    closeNewFolderDialog();
    setStatus('Created folder ' + (data.path || name), 'ready');
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
  }
}

export function initTree() {
  $('newFolderBtn').addEventListener('click', openNewFolderDialog);
  $('cancelNewFolder').addEventListener('click', closeNewFolderDialog);
  $('newFolderForm').addEventListener('submit', submitNewFolder);
  const off = [
    on(Events.ENTRY_OPENED, followEntry),
    // A save or create can change a folder's word counts, stub markers or entries.
    on(Events.VAULT_CHANGED, (detail) => refreshFolder(detail && detail.path ? parentOf(detail.path) : '')),
  ];
  return () => off.forEach((stop) => stop());
}
