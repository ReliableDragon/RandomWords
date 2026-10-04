// The World map: a force-laid-out graph around the open entry ("local"), or
// the whole vault as a political map ("atlas", drawn by world_atlas.js).

import { world } from './api.js';
import { rollPrompt } from './backlog.js';
import { openCreate } from './create.js';
import { $, button, h, textNode } from './dom.js';
import { openEntry } from './editor.js';
import { Events, on } from './events.js';
import { ghostCandidates, planGhosts } from './ghosts.js';
import { openReference } from './refcard.js';
import { state as shared } from './state.js';

const SVG_NS = 'http://www.w3.org/2000/svg';
const W = 900;
const H = 620;
const NUL = '\u0000';

const state = {
  mode: 'local', // 'local' (around the open entry) or 'atlas'
  current: null, // path of the open entry
  title: '',
  depth: 1, // links to follow in local mode
  nearby: {}, // Nearby groups, drawn as ghost nodes
  merged: null, // Nearby's one-card-per-entry list, best first, when it has one
  nearbyPath: null, // the entry those suggestions were computed for
  overlay: 'kind', // Atlas colouring: kind, orphans, stubs or rework
  graph: null,
  seq: 0, // guards against out-of-order graph responses
  raf: 0, // animation frame of the running layout
  nodes: [],
  edges: [],
  nodeEls: null, // Map id -> <g>
  edgeEls: null, // Map key -> <line>
  viewport: { scale: 1, tx: 0, ty: 0 },
  bounds: null,
  drag: null,
  moved: false,
  suppressClick: false, // set after dragging a node so the click is ignored
  layoutW: W,
  layoutH: H,
};

let svg = null;
let host = null;
let atlas = null;

// -- Small helpers -----------------------------------------------------------

function svgEl(tag, attrs, parent) {
  const node = document.createElementNS(SVG_NS, tag);
  Object.keys(attrs || {}).forEach((key) => node.setAttribute(key, attrs[key]));
  if (parent) parent.appendChild(node);
  return node;
}

const visible = () => !host.hidden;
const hint = (text) => { $('mapHint').textContent = text; };
const nodeName = (node) => node.title || node.id;

function stopLayout() {
  if (state.raf) cancelAnimationFrame(state.raf);
  state.raf = 0;
}

function fail(message) {
  stopLayout();
  $('mapLoading').hidden = true;
  svg.replaceChildren();
  hint(message);
}

function findNode(id) {
  return state.nodes.find((node) => node.id === id);
}

// -- Viewport (pan and zoom) -------------------------------------------------

function resetViewport() {
  state.viewport = { scale: 1, tx: 0, ty: 0 };
}

function applyViewport() {
  const root = svg.querySelector('.map-viewport');
  if (!root) return;
  const v = state.viewport;
  root.setAttribute('transform', 'translate(' + v.tx + ' ' + v.ty + ') scale(' + v.scale + ')');
}

function nodeBounds() {
  const xs = state.nodes.map((node) => node.x);
  const ys = state.nodes.map((node) => node.y);
  return {
    minX: Math.min(...xs) - 32, maxX: Math.max(...xs) + 32,
    minY: Math.min(...ys) - 36, maxY: Math.max(...ys) + 36,
  };
}

function fitViewport() {
  if (state.nodes.length) state.bounds = nodeBounds();
  const b = state.bounds;
  if (!b) {
    resetViewport();
    applyViewport();
    return;
  }
  const bw = Math.max(1, b.maxX - b.minX);
  const bh = Math.max(1, b.maxY - b.minY);
  const scale = Math.max(0.32, Math.min(2.2, (W - 44) / bw, (H - 44) / bh));
  state.viewport = {
    scale,
    tx: W / 2 - ((b.minX + b.maxX) / 2) * scale,
    ty: H / 2 - ((b.minY + b.maxY) / 2) * scale,
  };
  applyViewport();
}

// A pointer position in SVG (viewBox) coordinates.
function point(event) {
  const rect = svg.getBoundingClientRect();
  return { x: (event.clientX - rect.left) * W / rect.width, y: (event.clientY - rect.top) * H / rect.height };
}

function zoomAt(factor, anchor) {
  const before = state.viewport;
  const p = anchor || { x: W / 2, y: H / 2 };
  const scale = Math.max(0.45, Math.min(3.2, before.scale * factor));
  if (scale === before.scale) return;
  state.viewport = {
    scale,
    tx: p.x - (p.x - before.tx) * scale / before.scale,
    ty: p.y - (p.y - before.ty) * scale / before.scale,
  };
  applyViewport();
}

function startDrag(event) {
  if (event.button !== 0) return;
  const target = event.target.closest && event.target.closest('.map-node');
  const node = (target && target.__mapNode) || null;
  state.drag = {
    pointer: event.pointerId,
    start: point(event),
    origin: { tx: state.viewport.tx, ty: state.viewport.ty },
    node,
    nodeOrigin: node ? { x: node.x, y: node.y } : null,
  };
  state.moved = false;
  svg.setPointerCapture(event.pointerId);
  svg.classList.add('is-panning');
}

function moveDrag(event) {
  const drag = state.drag;
  if (!drag || drag.pointer !== event.pointerId) return;
  const p = point(event);
  const dx = p.x - drag.start.x;
  const dy = p.y - drag.start.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) state.moved = true;
  if (drag.node) {
    drag.node.x = drag.nodeOrigin.x + dx / state.viewport.scale;
    drag.node.y = drag.nodeOrigin.y + dy / state.viewport.scale;
    drag.node.vx = 0;
    drag.node.vy = 0;
    drag.node.fixed = true;
    updateGraphVisuals();
  } else {
    state.viewport.tx = drag.origin.tx + dx;
    state.viewport.ty = drag.origin.ty + dy;
    applyViewport();
  }
}

function endDrag(event) {
  if (!state.drag || state.drag.pointer !== event.pointerId) return;
  if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
  svg.classList.remove('is-panning');
  state.suppressClick = state.moved && Boolean(state.drag.node);
  state.drag = null;
}

// Handlers are assigned (not added) so redrawing never stacks them.
function attachViewport() {
  svg.onwheel = (event) => {
    event.preventDefault();
    zoomAt(event.deltaY < 0 ? 1.16 : 1 / 1.16, point(event));
  };
  svg.onpointerdown = startDrag;
  svg.onpointermove = moveDrag;
  svg.onpointerup = endDrag;
  svg.onpointercancel = endDrag;
}

// -- Loading the graph -------------------------------------------------------

function graphQuery() {
  if (state.mode === 'atlas') return {};
  return { around: state.current, depth: state.depth };
}

function fetchGraph() {
  if (state.mode === 'local' && !state.current) {
    fail('Open an entry to map its nearby links, or open the Atlas to see the whole world.');
    return Promise.resolve();
  }
  const mine = ++state.seq;
  $('mapLoading').hidden = false;
  return world.get('/graph', graphQuery()).then((data) => {
    if (mine !== state.seq) return;
    state.graph = data;
    if (state.mode === 'atlas') {
      showAtlas(data);
    } else {
      const nodes = (data.nodes || []).map((n) => Object.assign({}, n, { x: 0, y: 0, vx: 0, vy: 0 }));
      const edges = (data.edges || []).map((e) => Object.assign({}, e));
      addGhosts(nodes, edges);
      renderGraph(nodes, edges);
    }
    $('mapLoading').hidden = true;
  }).catch((error) => {
    if (mine === state.seq) fail(error.message);
  });
}

// Nearby suggestions appear as dashed "ghost" nodes linked to the open entry.
function addGhosts(nodes, edges) {
  planGhosts({
    current: state.current, nodes, edges,
    candidates: ghostCandidates({
      current: state.current, nearbyPath: state.nearbyPath, merged: state.merged, groups: state.nearby,
    }),
  });
}

// -- Drawing the local graph -------------------------------------------------

// Stable pseudo-random 0..1 from an id, so a node starts in the same place.
function seeded(id) {
  let x = 0;
  for (let i = 0; i < id.length; i++) x = (x * 31 + id.charCodeAt(i)) | 0;
  return Math.abs(x % 10000) / 10000;
}

function nodeColor(node) {
  if (node.color) return node.color;
  if (node.state === 'unresolved') return '#bf5b48';
  return node.state === 'ambiguous' ? '#b6813d' : '#5b7e75';
}

function initPositions(nodes) {
  const lw = state.layoutW;
  const lh = state.layoutH;
  nodes.forEach((n, i) => {
    const angle = seeded(n.id || n.path || n.title) * Math.PI * 2 + i * 0.09;
    const radius = 65 + seeded((n.id || '') + 'r') * Math.min(lw, lh) * 0.38;
    n.x = lw / 2 + Math.cos(angle) * radius;
    n.y = lh / 2 + Math.sin(angle) * radius;
  });
  const center = nodes.find((n) => n.path === state.current);
  if (center) {
    center.x = lw / 2;
    center.y = lh / 2;
  }
}

const lineKey = (edge) => edge.source + NUL + edge.target + NUL + edge.status;

function hexagonPoints(x, y, radius) {
  const points = [];
  for (let i = 0; i < 6; i++) {
    const angle = Math.PI / 3 * i;
    points.push((x + Math.cos(angle) * radius) + ',' + (y + Math.sin(angle) * radius));
  }
  return points.join(' ');
}

function nodeClasses(node, dense) {
  return 'map-node state-' + (node.state || 'entry')
    + (node.stub ? ' is-stub' : '') + (node.rework ? ' is-rework' : '')
    + (node.ghost ? ' is-ghost' : '') + (node.path && node.path === state.current ? ' is-current' : '')
    + (dense ? ' is-dense-label' : '');
}

function nodeAriaLabel(node) {
  return nodeName(node) + (node.path ? ' — ' + node.path : '')
    + (node.state === 'ambiguous' ? ' — ambiguous' : '') + (node.stub ? ' — stub' : '')
    + (node.rework ? ' — marked for rework' : '') + (node.ghost && node.why ? ' — suggested: ' + node.why : '');
}

function nodeRadius(node, dense) {
  const links = Math.sqrt(Math.max(0, node.inbound || 0));
  return Math.max(6, dense ? Math.min(12, 6 + links * 1.5) : Math.min(17, 7 + links * 2));
}

// The shape encodes state: hexagon ambiguous, square unresolved, else circle.
function nodeCore(node, size, parent) {
  if (node.state === 'ambiguous') return svgEl('polygon', { class: 'map-node-core', points: hexagonPoints(node.x, node.y, size) }, parent);
  if (node.state === 'unresolved') {
    return svgEl('rect', {
      class: 'map-node-core', x: node.x - size * 0.72, y: node.y - size * 0.72, width: size * 1.44, height: size * 1.44, rx: 1,
    }, parent);
  }
  return svgEl('circle', { class: 'map-node-core', cx: node.x, cy: node.y, r: size }, parent);
}

function activateNode(node, event) {
  if (state.suppressClick) {
    state.suppressClick = false;
    return;
  }
  selectNode(node);
  if (!node.path) return;
  if (event.shiftKey || event.metaKey || event.ctrlKey) openReference(node.path);
  else openEntry(node.path);
}

function drawNode(node, layer, dense) {
  const g = svgEl('g', { class: nodeClasses(node, dense) }, layer);
  g.__mapNode = node;
  g.style.setProperty('--node-color', nodeColor(node));
  g.setAttribute('tabindex', '0');
  g.setAttribute('role', 'button');
  g.setAttribute('aria-label', nodeAriaLabel(node));
  svgEl('title', {}, g).textContent = nodeName(node) + (node.path ? ' · ' + node.path : '')
    + (node.ghost && node.why ? '\nSuggested: ' + node.why : '');
  const size = nodeRadius(node, dense);
  node.radius = size;
  nodeCore(node, size, g);
  if (node.rework) svgEl('circle', { class: 'map-rework-ring', cx: node.x, cy: node.y, r: size + 4 }, g);
  const name = nodeName(node) || '';
  svgEl('text', { class: 'map-node-label', x: node.x, y: node.y + size + 13 }, g).textContent =
    name.length > 28 ? name.slice(0, 26) + '…' : name;
  g.addEventListener('click', (event) => activateNode(node, event));
  g.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    if (node.path) openEntry(node.path);
    else selectNode(node);
  });
  return g;
}

function renderGraph(nodes, edges) {
  atlas.detach();
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  state.nodes = nodes;
  state.edges = edges;
  resetViewport();
  initPositions(nodes);
  svg.replaceChildren();
  const viewport = svgEl('g', { class: 'map-viewport' }, svg);
  const edgeLayer = svgEl('g', { class: 'map-edges' }, viewport);
  const nodeLayer = svgEl('g', { class: 'map-nodes' }, viewport);
  const edgeEls = new Map();
  const nodeEls = new Map();
  const dense = nodes.length > 46;
  edges.forEach((edge) => {
    const a = findNode(edge.source);
    const b = findNode(edge.target);
    if (!a || !b) return;
    const line = svgEl('line', { class: 'map-edge is-' + edge.status, x1: a.x, y1: a.y, x2: b.x, y2: b.y }, edgeLayer);
    if (edge.label) line.setAttribute('aria-label', edge.label);
    if (edge.status === 'ghost' && edge.label) svgEl('title', {}, line).textContent = 'Suggested: ' + edge.label;
    edgeEls.set(lineKey(edge), line);
  });
  nodes.forEach((node) => nodeEls.set(node.id, drawNode(node, nodeLayer, dense)));
  state.nodeEls = nodeEls;
  state.edgeEls = edgeEls;
  attachViewport();
  fitViewport();
  hint('Around ' + (state.title || state.current) + ' · ' + state.depth + ' link' + (state.depth === 1 ? '' : 's')
    + ' · ' + nodes.length + ' nodes · ' + edges.length + ' links. Select a note to open; Shift-click to preview.');
  simulate(nodes, edges);
}

// -- Force layout ------------------------------------------------------------

const CHARGE = 1300;
const GRAVITY = 0.0008;
const FRAMES = 90;

function repel(nodes, alpha, lw, lh) {
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    a.vx += (lw / 2 - a.x) * GRAVITY * alpha / 0.12;
    a.vy += (lh / 2 - a.y) * GRAVITY * alpha / 0.12;
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const force = CHARGE / (dx * dx + dy * dy + 1) * alpha / 0.12;
      a.vx += dx * force;
      a.vy += dy * force;
      b.vx -= dx * force;
      b.vy -= dy * force;
    }
  }
}

function attract(edges, alpha) {
  edges.forEach((edge) => {
    if (edge.status !== 'resolved' && edge.status !== 'ghost') return;
    const a = findNode(edge.source);
    const b = findNode(edge.target);
    if (!a || !b) return;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.sqrt(dx * dx + dy * dy) || 1;
    const rest = edge.status === 'ghost' ? 145 : 105;
    const force = (distance - rest) * 0.0007 * alpha / 0.12;
    a.vx += dx * force;
    a.vy += dy * force;
    b.vx -= dx * force;
    b.vy -= dy * force;
  });
}

function settle(nodes, center, lw, lh) {
  nodes.forEach((p) => {
    if (p === center) {
      p.x = lw / 2;
      p.y = lh / 2;
      p.vx = 0;
      p.vy = 0;
    } else if (!p.fixed) {
      p.vx *= 0.84;
      p.vy *= 0.84;
      p.x = Math.max(24, Math.min(lw - 24, p.x + p.vx));
      p.y = Math.max(28, Math.min(lh - 30, p.y + p.vy));
    }
  });
}

// Runs the layout for FRAMES animation frames, cooling as it goes.
function simulate(nodes, edges) {
  stopLayout();
  const center = nodes.find((n) => n.path === state.current);
  const lw = state.layoutW;
  const lh = state.layoutH;
  let tick = 0;
  function frame() {
    tick++;
    const alpha = Math.max(0, 0.12 * (1 - tick / FRAMES));
    if (alpha <= 0) return;
    repel(nodes, alpha, lw, lh);
    attract(edges, alpha);
    settle(nodes, center, lw, lh);
    updateGraphVisuals();
    state.raf = requestAnimationFrame(frame);
  }
  state.raf = requestAnimationFrame(frame);
}

function moveNodeVisual(node) {
  const g = state.nodeEls.get(node.id);
  if (!g) return;
  const core = g.querySelector('.map-node-core');
  if (core.tagName === 'circle') {
    core.setAttribute('cx', node.x);
    core.setAttribute('cy', node.y);
  } else if (core.tagName === 'rect') {
    core.setAttribute('x', node.x - node.radius * 0.72);
    core.setAttribute('y', node.y - node.radius * 0.72);
  } else {
    core.setAttribute('points', hexagonPoints(node.x, node.y, node.radius));
  }
  const ring = g.querySelector('.map-rework-ring');
  if (ring) {
    ring.setAttribute('cx', node.x);
    ring.setAttribute('cy', node.y);
  }
  const label = g.querySelector('.map-node-label');
  label.setAttribute('x', node.x);
  label.setAttribute('y', node.y + node.radius + 13);
}

function updateGraphVisuals() {
  if (!state.nodeEls || !state.edgeEls) return;
  state.nodes.forEach(moveNodeVisual);
  state.edges.forEach((edge) => {
    const line = state.edgeEls.get(lineKey(edge));
    const a = findNode(edge.source);
    const b = findNode(edge.target);
    if (!line || !a || !b) return;
    line.setAttribute('x1', a.x);
    line.setAttribute('y1', a.y);
    line.setAttribute('x2', b.x);
    line.setAttribute('y2', b.y);
  });
}

// -- Selection panel ---------------------------------------------------------

function candidateList(box, candidates) {
  (candidates || []).forEach((path) => box.appendChild(button(path, 'report-entry-link', () => openEntry(path))));
}

function describeEntryNode(box, node) {
  box.appendChild(textNode('strong', node.title || node.path));
  box.appendChild(textNode('small', node.path, 'map-selected-path'));
  if (node.ghost && node.why) box.appendChild(textNode('small', 'Suggested: ' + node.why, 'map-selected-path'));
  if (node.state === 'ambiguous' && node.candidates && node.candidates.length) {
    box.appendChild(textNode('p', 'Ambiguous target. Candidate notes:', 'muted'));
    candidateList(box, node.candidates);
    return;
  }
  box.appendChild(button('Open entry', 'btn btn-small btn-primary', () => openEntry(node.path)));
  box.appendChild(button('Preview', 'btn btn-small btn-quiet', () => openReference(node.path)));
}

function describeUnresolvedNode(box, node) {
  box.appendChild(textNode('strong', node.title || node.id));
  box.appendChild(textNode('small', node.state === 'ambiguous' ? 'Ambiguous wikilink' : 'Unresolved wikilink', 'map-selected-path'));
  candidateList(box, node.candidates);
}

function selectNode(node) {
  if (state.nodeEls) state.nodeEls.forEach((g) => g.classList.toggle('is-selected', g.__mapNode === node));
  const box = $('mapSelection');
  box.replaceChildren();
  if (node.path) describeEntryNode(box, node);
  else describeUnresolvedNode(box, node);
}

// -- Atlas -------------------------------------------------------------------

function territoryOptions(select, realms) {
  select.replaceChildren(new Option('Go to a territory…', ''));
  realms.forEach((realm) => {
    const group = h('optgroup', { label: realm.name });
    realm.territories.forEach((territory) => {
      group.appendChild(new Option(territory.name + ' · ' + territory.count, territory.id));
    });
    select.appendChild(group);
  });
}

function atlasSummaryText(summary) {
  const left = summary.hidden ? ' · ' + summary.hidden + ' templates, ideas and loose notes left out' : '';
  return 'Atlas · ' + summary.entries + ' entries in ' + summary.territories + ' territories across '
    + summary.realms + ' realms' + left + '.';
}

function showAtlas(data) {
  stopLayout();
  state.nodes = [];
  state.edges = [];
  state.nodeEls = null;
  state.edgeEls = null;
  $('mapSelection').replaceChildren();
  atlas.show(data);
  const summary = atlas.summary();
  const select = $('mapTerritory');
  territoryOptions(select, summary.realmList);
  select.value = atlas.selectedTerritory();
  hint(summary.entries ? atlasSummaryText(summary) : 'No world entries to map yet.');
  renderOverlayLegend();
}

// -- Atlas colouring and the open entry --------------------------------------

const OVERLAY_TITLES = {
  kind: 'Coloured by kind', orphans: 'Orphans: entries nothing links to',
  stubs: 'Stubs', rework: 'Marked for rework',
};

function renderOverlayLegend() {
  const box = $('mapOverlayLegend');
  const info = state.mode === 'atlas' ? atlas.legend() : null;
  box.hidden = !info;
  if (!info) return;
  box.setAttribute('data-mode', info.mode);
  box.replaceChildren(textNode('strong', (OVERLAY_TITLES[info.mode] || '') + ' · ' + info.total + ' entries'));
  info.items.forEach((item) => {
    const swatch = h('i', { class: 'legend-swatch is-' + item.swatch });
    if (item.color) swatch.style.setProperty('--swatch', item.color);
    box.appendChild(h('span', null, swatch, item.label + ' · ' + item.count));
  });
}

function setOverlay(mode) {
  state.overlay = mode;
  document.querySelectorAll('[data-map-overlay]').forEach((b) => {
    b.setAttribute('aria-pressed', b.dataset.mapOverlay === mode ? 'true' : 'false');
  });
  atlas.setOverlay(mode);
  renderOverlayLegend();
}

function findOpenEntry() {
  if (!state.current) {
    hint('No entry is open. Open one from the file tree, then find it here.');
  } else if (!atlas.flyToOpen()) {
    hint((state.title || state.current) + ' is not on the Atlas: templates, ideas and loose notes are left out.');
  }
}

function syncOpenControls() {
  $('mapFindOpen').disabled = !state.current;
}

const GESTURE_HELP = {
  atlas: 'Scroll to zoom and drag to pan. Click land to open a territory; hover a dot to trace its links, click it for details, double-click or press Enter to open it.',
  local: 'Scroll to zoom. Drag the canvas to pan; drag a node to arrange it. Click a node or press Enter to open it.',
};

function setMode(mode) {
  state.mode = mode;
  const isAtlas = mode === 'atlas';
  document.querySelector('.map-layout').classList.toggle('is-atlas', isAtlas);
  $('mapGesture').textContent = GESTURE_HELP[mode];
  document.querySelectorAll('[data-map-mode]').forEach((b) => {
    b.setAttribute('aria-pressed', b.dataset.mapMode === mode ? 'true' : 'false');
  });
  $('mapDepthControl').hidden = isAtlas;
  $('mapTerritoryControl').hidden = !isAtlas;
  $('mapLegend').hidden = isAtlas;
  $('mapAtlasLegend').hidden = !isAtlas;
  $('mapOverlayControl').hidden = !isAtlas;
  $('mapFindOpen').hidden = !isAtlas;
  if (!isAtlas) $('mapOverlayLegend').hidden = true;
  if (!isAtlas) atlas.detach();
  fetchGraph();
}

// -- Wiring ------------------------------------------------------------------

function zoomControl(factor) {
  if (state.mode === 'atlas') atlas.zoomBy(factor);
  else zoomAt(factor);
}

function bindControls() {
  document.querySelectorAll('[data-map-mode]').forEach((b) => {
    b.addEventListener('click', () => setMode(b.dataset.mapMode));
  });
  $('mapDepth').addEventListener('change', (event) => {
    state.depth = event.target.value === '2' ? 2 : 1;
    if (state.mode === 'local') fetchGraph();
  });
  $('mapTerritory').addEventListener('change', (event) => {
    if (state.mode === 'atlas') atlas.goTo(event.target.value);
  });
  document.querySelectorAll('[data-map-overlay]').forEach((b) => {
    b.addEventListener('click', () => setOverlay(b.dataset.mapOverlay));
  });
  $('mapFindOpen').addEventListener('click', findOpenEntry);
  $('mapZoomIn').addEventListener('click', () => zoomControl(1.25));
  $('mapZoomOut').addEventListener('click', () => zoomControl(1 / 1.25));
  $('mapFit').addEventListener('click', () => {
    if (state.mode === 'atlas') atlas.fit();
    else fitViewport();
  });
  $('refreshMap').addEventListener('click', () => {
    state.graph = null;
    setMode(state.mode);
  });
  window.addEventListener('resize', () => {
    if (visible() && state.mode === 'atlas') atlas.resize();
  });
}

// Registered with the view switcher: draws the map whenever it is shown.
export const mapView = {
  load() {
    if (svg) fetchGraph();
  },
};

export function initMap() {
  svg = $('worldMapSvg');
  host = $('mapView');
  if (!svg || !host) return;
  atlas = window.WorldAtlas.create({
    svg,
    panel: $('mapAtlasPanel'),
    open: (path) => { if (path) openEntry(path); },
    preview: openReference,
    onTerritory: (id) => { $('mapTerritory').value = id; },
    roll: (path) => rollPrompt({ entry: path }),
    create: (prefill) => openCreate(prefill),
  });
  bindControls();
  syncOpenControls();
  on(Events.ENTRY_OPENED, (detail) => {
    state.current = (detail && detail.path) || null;
    state.title = (detail && detail.title) || state.current || '';
    atlas.setOpen(state.current);
    syncOpenControls();
    if (visible() && state.mode === 'local') fetchGraph();
  });
  on(Events.NEARBY_UPDATED, (detail) => {
    state.nearby = (detail && detail.groups) || {};
    state.merged = (detail && detail.merged) || (shared.nearby && shared.nearby.merged) || null;
    state.nearbyPath = (detail && detail.path) || state.current;
    if (visible() && state.mode === 'local') fetchGraph();
  });
}
