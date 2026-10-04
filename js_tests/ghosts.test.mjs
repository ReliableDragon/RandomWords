import test from 'node:test';
import assert from 'node:assert/strict';

import { GHOST_LIMIT, ghostCandidates, planGhosts } from '../static/world/ghosts.js';

const card = (n, score, text) => ({
  path: 'Flora/E' + n + '.md', title: 'E' + n, score, reasons: [{ group: 'same_tags', text }],
});

test('at most eight ghosts, best merged score first, each with its first reason', () => {
  const merged = [];
  for (let i = 0; i < 23; i++) merged.push(card(i, i, 'Because ' + i));
  const nodes = [{ id: 'Me.md', path: 'Me.md', title: 'Me' }];
  const edges = [];
  const candidates = ghostCandidates({ current: 'Me.md', nearbyPath: 'Me.md', merged, groups: {} });
  planGhosts({ current: 'Me.md', nodes, edges, candidates });
  const ghosts = nodes.filter((n) => n.ghost);
  assert.equal(GHOST_LIMIT, 8);
  assert.equal(ghosts.length, 8);
  assert.deepEqual(ghosts.map((n) => n.title), ['E22', 'E21', 'E20', 'E19', 'E18', 'E17', 'E16', 'E15']);
  assert.equal(ghosts[0].why, 'Because 22');
  assert.equal(edges.length, 8);
  assert.equal(edges[0].label, 'Because 22');
});

test('entries already linked, or the open entry itself, are not ghosts and do not use the cap', () => {
  const merged = [card(0, 9, 'x'), card(1, 8, 'y'), { path: 'Me.md', title: 'Me', score: 99, reasons: [] }];
  const nodes = [{ id: 'Me.md', path: 'Me.md' }, { id: 'Flora/E0.md', path: 'Flora/E0.md', title: 'E0' }];
  const edges = [{ source: 'Me.md', target: 'Flora/E0.md', status: 'resolved' }];
  planGhosts({
    current: 'Me.md', nodes, edges,
    candidates: ghostCandidates({ current: 'Me.md', nearbyPath: 'Me.md', merged, groups: {} }),
  });
  assert.deepEqual(nodes.filter((n) => n.ghost).map((n) => n.path), ['Flora/E1.md']);
});

test('suggestions computed for another entry are ignored', () => {
  assert.deepEqual(ghostCandidates({ current: 'B.md', nearbyPath: 'A.md', merged: [card(1, 1, 'x')], groups: {} }), []);
});

test('without a merged list the groups are used, and an entry in two groups keeps both reasons', () => {
  const groups = {
    same_tags: [{ path: 'A.md', title: 'A' }],
    same_biome: [{ path: 'A.md', title: 'A' }, { path: 'B.md', title: 'B' }],
  };
  const nodes = [{ id: 'Me.md', path: 'Me.md' }];
  const edges = [];
  planGhosts({
    current: 'Me.md', nodes, edges,
    candidates: ghostCandidates({ current: 'Me.md', nearbyPath: 'Me.md', merged: null, groups }),
  });
  assert.equal(nodes.filter((n) => n.ghost).length, 2);
  assert.equal(edges.find((e) => e.target === 'A.md').label, 'same tags, same biome');
});
