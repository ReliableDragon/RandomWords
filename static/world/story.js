// Story: scenes ordered by their story metadata, with who and where.

import { world } from './api.js';
import { $, button, h, setStatus, textNode } from './dom.js';
import { openEntry } from './editor.js';
import { loadVoiceQuotes, openReference } from './refcard.js';
import { createReportView } from './report.js';
import { diagnosticText, entryTitle, exportFilename, isPeoplePath } from './text.js';

const openScene = (path) => { if (path) openEntry(path); };
const previewEntry = (path) => { if (path) openReference(path); };

function diagnosticsBox(diagnostics) {
  const list = Array.isArray(diagnostics) ? diagnostics : [];
  if (!list.length) return null;
  return h('div', { class: 'story-diagnostics' },
    textNode('strong', 'Diagnostics'),
    h('ul', null, list.map((item) => textNode('li', diagnosticText(item)))));
}

function referenceItem(ref) {
  const path = ref.path || '';
  const label = ref.title || ref.target || entryTitle({ path }) || 'Unresolved reference';
  const nodes = [path
    ? button(label, 'story-reference', () => previewEntry(path))
    : textNode('span', label, 'story-unresolved')];
  if (ref.diagnostic) nodes.push(textNode('small', ref.diagnostic, 'report-path'));
  return nodes;
}

function referencesSection(label, refs) {
  const list = Array.isArray(refs) ? refs : [];
  if (!list.length) return null;
  return h('section', { class: 'story-metadata' },
    textNode('h4', label),
    h('div', { class: 'story-reference-list' }, list.map(referenceItem)));
}

function voiceControls(path) {
  const quotes = h('div', { class: 'story-quotes', hidden: true });
  const toggle = button('Voice', 'text-button story-voice-toggle', () => {
    quotes.hidden = !quotes.hidden;
    if (!quotes.hidden && !quotes.dataset.loaded) {
      quotes.dataset.loaded = 'yes';
      loadVoiceQuotes(quotes, path);
    }
  });
  return [toggle, quotes];
}

function appearanceRow(person) {
  return h('div', { class: 'story-appearance' },
    button(person.title || entryTitle(person), 'story-reference', () => previewEntry(person.path)),
    isPeoplePath(person.path) ? voiceControls(person.path) : null);
}

function appearancesSection(appearances) {
  const list = Array.isArray(appearances) ? appearances : [];
  if (!list.length) return null;
  return h('section', { class: 'story-metadata' },
    textNode('h4', 'Entries mentioned'),
    h('div', { class: 'story-appearance-list' }, list.map(appearanceRow)));
}

function sceneLinks(item, titles) {
  const later = Array.isArray(item.later_scenes) ? item.later_scenes : [];
  const links = h('span', { class: 'story-scene-links' });
  [item.first_scene].concat(later).filter(Boolean).forEach((path, index) => {
    if (index) links.appendChild(document.createTextNode(' · '));
    const label = (index ? 'Later: ' : 'First: ') + (titles[path] || entryTitle({ path }));
    links.appendChild(button(label, 'report-entry-link', () => openScene(path)));
  });
  return links;
}

function globalAppearances(appearances, scenes) {
  const list = Array.isArray(appearances) ? appearances : [];
  if (!list.length) return null;
  const titles = {};
  (scenes || []).forEach((scene) => { titles[scene.path] = scene.title || entryTitle(scene); });
  return h('section', { class: 'story-global-appearances report-card' },
    textNode('h3', 'Appearance report'),
    list.map((item) => h('div', { class: 'story-global-appearance' },
      button(item.title || entryTitle(item), 'story-reference', () => previewEntry(item.path)),
      sceneLinks(item, titles))));
}

const START_COMMAND = 'python3 serve.py --vault ~/Documents/Worldbuilding --story-folder Story';
const METADATA_HELP = 'A scene is a note in one of those folders whose frontmatter has '
  + 'when: 3 for its order, plus where: and who: with [[links]] to the places and people it involves.';

// Story has nothing to show either because no folder was passed at startup
// or because the folders hold no scenes yet; the fix differs, so say which.
export function storyEmptyState(folders) {
  const list = Array.isArray(folders) ? folders : [];
  if (!list.length) return { configured: false, folders: [] };
  return { configured: true, folders: list };
}

function emptyStory(folders) {
  const state = storyEmptyState(folders);
  if (state.configured) {
    return h('div', { class: 'story-empty report-card' },
      textNode('h3', 'No scenes yet'),
      textNode('p', 'Story is reading ' + state.folders.join(', ') + ', but no notes there have story metadata.'),
      textNode('p', METADATA_HELP));
  }
  return h('div', { class: 'story-empty report-card' },
    textNode('h3', 'No story folders are set up'),
    textNode('p', 'Story reads the folders you pass with --story-folder when you start the server. '
      + 'Name each folder relative to the vault, and repeat the option for more than one.'),
    h('pre', { class: 'story-command' }, START_COMMAND),
    textNode('p', METADATA_HELP));
}

function folderExports(folders) {
  if (!folders.length) return null;
  return h('div', { class: 'story-folder-exports' },
    textNode('span', 'Export folder:', 'report-path'),
    folders.map((folder) => {
      const trigger = button(folder, 'btn btn-small btn-quiet', () => exportStory(folder, trigger));
      return trigger;
    }));
}

function sceneCard(scene, index) {
  const order = scene.when == null ? index + 1 : scene.when;
  return h('article', { class: 'story-scene report-card' },
    h('div', { class: 'story-scene-head' },
      textNode('span', String(order), 'story-order'),
      button(scene.title || entryTitle(scene), 'story-scene-title', () => openScene(scene.path))),
    textNode('small', scene.path, 'report-path'),
    diagnosticsBox(scene.diagnostics),
    referencesSection('Where', scene.where),
    referencesSection('Who', scene.who),
    appearancesSection(scene.appearances));
}

function renderStory(data) {
  const scenes = Array.isArray(data.scenes) ? data.scenes : [];
  const folders = Array.isArray(data.folders) ? data.folders : [];
  const fragment = document.createDocumentFragment();
  [
    scenes.length ? folderExports(folders) : null,
    diagnosticsBox(data.diagnostics),
    globalAppearances(data.appearances, scenes),
    scenes.length ? null : emptyStory(folders),
    ...scenes.map(sceneCard),
  ].forEach((node) => { if (node) fragment.appendChild(node); });
  $('storyContent').replaceChildren(fragment);
}

export const story = createReportView({
  hostId: 'storyContent',
  loadingText: 'Loading story…',
  getData: () => world.get('/story'),
  render: renderStory,
});

export const load = story.load;

function download(filename, html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = h('a', { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Exports a reading copy: all scenes ('story') or one story folder.
export async function exportStory(path, sourceButton) {
  const trigger = sourceButton || $('exportStory');
  const previous = trigger.textContent;
  trigger.disabled = true;
  trigger.textContent = 'Preparing…';
  try {
    const data = await world.get('/export', { path });
    download(exportFilename(data.filename || path, 'story'), data.html || '');
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    trigger.disabled = false;
    trigger.textContent = previous;
  }
}

export function initStory() {
  $('refreshStory').addEventListener('click', () => story.load({ force: true }));
  $('exportStory').addEventListener('click', () => exportStory('story'));
}
