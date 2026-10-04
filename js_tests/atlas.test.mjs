import test from 'node:test';
import assert from 'node:assert/strict';

import { Element, findAll, installFakeDom, uninstallFakeDom } from './fake_dom.mjs';

globalThis.setTimeout = ((real) => (fn, ms) => { const t = real(fn, ms); t.unref(); return t; })(globalThis.setTimeout);

// world_atlas.js is a classic script that attaches WorldAtlas to window.
globalThis.window = globalThis.window || {};
await import('../static/world_atlas.js');
const { WorldAtlas } = globalThis.window;

const BIOME = 'Locations/Biomes/Forest-Jungle/Marsh.md';

function entry(path, extra) {
  const parts = path.split('/');
  return Object.assign({
    id: path, path, title: parts[parts.length - 1].replace(/\.md$/, ''), kind: parts[0], folder: parts.slice(0, -1).join('/'),
    state: 'entry', world: true, stub: false, rework: false, inbound: 1, biomes: [], color: null,
  }, extra);
}

function sampleGraph() {
  const nodes = [
    entry(BIOME, { kind: 'Locations', inbound: 4 }),
    entry('Flora and Fauna/Reed.md', { biomes: [{ path: BIOME, via: 'from' }], inbound: 0, color: '#5b7e75' }),
    entry('Flora and Fauna/Sedge.md', { biomes: [{ path: BIOME, via: 'from' }], stub: true, color: '#5b7e75' }),
    entry('Flora and Fauna/Cattail.md', { biomes: [{ path: BIOME, via: 'from' }], rework: true, inbound: 0, color: '#5b7e75' }),
    entry('Cultures/Fenfolk.md', { kind: 'Cultures', inbound: 2, color: '#c08040' }),
    entry('Cultures/Boatmen.md', { kind: 'Cultures', inbound: 0 }),
    entry('Cultures/Weirs.md', { kind: 'Cultures', inbound: 1 }),
    entry('Cultures/Reeds.md', { kind: 'Cultures', inbound: 1 }),
  ];
  const edges = [
    { source: 'Flora and Fauna/Reed.md', target: BIOME, status: 'resolved' },
    { source: 'Cultures/Fenfolk.md', target: 'Flora and Fauna/Sedge.md', status: 'resolved' },
  ];
  return { nodes, edges };
}

// A fake page: an svg with a size, and a panel.
function makeAtlas(options) {
  const dom = installFakeDom();
  const svg = new Element('svg');
  svg.getBoundingClientRect = () => ({ width: 900, height: 600, left: 0, top: 0 });
  const panel = new Element('aside');
  panel.hidden = true;
  panel.contains = () => false;
  Object.assign(globalThis, {
    matchMedia: () => ({ matches: true }),
    cancelAnimationFrame() {},
    requestAnimationFrame: () => 0,
    getComputedStyle: () => ({ position: 'static' }),
  });
  const calls = { rolled: [], created: [], opened: [] };
  const atlas = WorldAtlas.create(Object.assign({
    svg, panel, open: (path) => calls.opened.push(path), preview() {},
    roll: (path) => calls.rolled.push(path), create: (prefill) => calls.created.push(prefill),
  }, options));
  atlas.show(sampleGraph());
  return { atlas, svg, panel, calls, dom };
}

function teardown() {
  uninstallFakeDom();
  delete globalThis.matchMedia;
  delete globalThis.cancelAnimationFrame;
  delete globalThis.requestAnimationFrame;
  delete globalThis.getComputedStyle;
}

const buttonNamed = (panel, text) => findAll(panel, (n) => n.tagName === 'button' && n.textContent === text)[0];

test('the legend counts kinds by default and orphans, stubs and rework when asked', () => {
  const { atlas, svg } = makeAtlas();
  try {
    const kinds = atlas.legend();
    assert.equal(kinds.mode, 'kind');
    assert.equal(kinds.total, 8);
    assert.deepEqual(kinds.items.map((i) => [i.label, i.count]),
      [['Cultures', 4], ['Flora and Fauna', 3], ['Locations', 1]]);
    assert.equal(kinds.items[1].color, '#5b7e75');
    assert.equal(svg.dataset.overlay, undefined);

    atlas.setOverlay('orphans');
    assert.equal(svg.dataset.overlay, 'orphans');
    assert.deepEqual(atlas.legend().items.map((i) => [i.label, i.count]), [['No inbound links', 3], ['Linked to', 5]]);
    atlas.setOverlay('stubs');
    assert.deepEqual(atlas.legend().items.map((i) => i.count), [1, 7]);
    atlas.setOverlay('rework');
    assert.deepEqual(atlas.legend().items.map((i) => i.count), [1, 7]);
    atlas.setOverlay('kind');
    assert.equal(svg.dataset.overlay, undefined);
  } finally {
    teardown();
  }
});

test('the open entry gets a ring, and Find open entry selects it', () => {
  const { atlas, svg, panel } = makeAtlas();
  try {
    const ring = () => findAll(svg, (n) => n.classList.contains('atlas-open-ring'))[0];
    assert.equal(ring().style.display, 'none');
    atlas.setOpen('Flora and Fauna/Reed.md');
    assert.equal(ring().style.display, '');
    assert.ok(Number(ring().getAttribute('r')) > 4);
    const dots = findAll(svg, (n) => n.classList.contains('atlas-node'));
    const open = dots.filter((n) => n.classList.contains('is-open'));
    assert.equal(open.length, 1);
    assert.match(open[0].getAttribute('aria-label'), /Reed.*open in the editor/);
    assert.equal(atlas.flyToOpen(), true);
    assert.equal(panel.hidden, false);
    assert.match(panel.textContent, /Reed/);
    // An entry that is not on the map (or nothing open) leaves the ring hidden.
    atlas.setOpen('Templates/Creature.md');
    assert.equal(ring().style.display, 'none');
    assert.equal(atlas.flyToOpen(), false);
    atlas.setOpen(null);
    assert.equal(dots.filter((n) => n.classList.contains('is-open')).length, 0);
  } finally {
    teardown();
  }
});

test('a biome territory offers Roll here and Start entry here with that biome as the From target', () => {
  const { atlas, panel, calls } = makeAtlas();
  try {
    atlas.goTo(BIOME);
    const roll = buttonNamed(panel, 'Roll here');
    const start = buttonNamed(panel, 'Start entry here');
    assert.ok(buttonNamed(panel, 'Open biome note'));
    roll.click();
    assert.equal(calls.rolled.length, 1);
    assert.ok(['Flora and Fauna/Reed.md', 'Flora and Fauna/Sedge.md', 'Flora and Fauna/Cattail.md', BIOME]
      .includes(calls.rolled[0]));
    start.click();
    assert.deepEqual(calls.created, [{ fromTargets: [BIOME] }]);
  } finally {
    teardown();
  }
});

test('a folder territory starts entries in its folder and rolls only its own entries', () => {
  const { atlas, panel, calls } = makeAtlas();
  try {
    atlas.goTo('folder:Cultures');
    buttonNamed(panel, 'Start entry here').click();
    assert.deepEqual(calls.created, [{ folder: 'Cultures' }]);
    buttonNamed(panel, 'Roll here').click();
    assert.match(calls.rolled[0], /^Cultures\//);
    assert.equal(buttonNamed(panel, 'Open biome note'), undefined);
  } finally {
    teardown();
  }
});
