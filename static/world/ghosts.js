// Which Nearby suggestions the local map draws as ghost nodes. No DOM here.

// Nearby can suggest dozens of entries; a fan of more than a few is unreadable.
export const GHOST_LIMIT = 8;

const NUL = '\u0000';

const titleFromPath = (path) => path.split('/').pop().replace(/\.md$/i, '');

function ghostNode(path, item) {
  return {
    id: path, path, title: item.title || titleFromPath(path),
    kind: item.kind || null, folder: item.folder || null, state: 'entry',
    stub: false, rework: false, inbound: 0, biomes: item.biomes || [], color: null,
    ghost: true, x: 0, y: 0, vx: 0, vy: 0,
  };
}

// Suggestions for the open entry, best first, each with the reason to show.
// `merged` is Nearby's one-card-per-entry list; without it the groups are used.
export function ghostCandidates({ current, nearbyPath, merged, groups }) {
  // Suggestions computed for another entry say nothing about this one.
  if (nearbyPath !== current) return [];
  if (merged && merged.length) {
    return merged.slice().sort((a, b) => (b.score || 0) - (a.score || 0)).map((card) => ({
      path: card.path, item: card, why: (card.reasons && card.reasons[0] && card.reasons[0].text) || '',
    }));
  }
  const list = [];
  Object.keys(groups || {}).forEach((group) => {
    (groups[group] || []).forEach((item) => {
      list.push({ path: item.path, item, why: group.replace(/_/g, ' ') });
    });
  });
  return list;
}

function addGhostEdge(edges, current, path, label) {
  const prior = edges.find((e) => e.status === 'ghost' && e.source === current && e.target === path);
  if (!prior) {
    edges.push({ source: current, target: path, status: 'ghost', label });
  } else if (label && prior.label.indexOf(label) < 0) {
    prior.label += ', ' + label;
  }
}

// Adds ghost nodes and edges in place: at most GHOST_LIMIT entries, none already linked.
export function planGhosts({ current, nodes, edges, candidates }) {
  if (!current) return;
  const byPath = new Map(nodes.filter((n) => n.path).map((n) => [n.path, n]));
  const linked = new Set(edges.filter((e) => e.status === 'resolved').map((e) => e.source + NUL + e.target));
  const chosen = new Set();
  candidates.forEach(({ path, item, why }) => {
    if (!path || path === current) return;
    if (linked.has(current + NUL + path) || linked.has(path + NUL + current)) return;
    if (!chosen.has(path) && chosen.size >= GHOST_LIMIT) return;
    chosen.add(path);
    let node = byPath.get(path);
    if (!node) {
      node = ghostNode(path, item);
      nodes.push(node);
      byPath.set(path, node);
    }
    node.ghost = true;
    node.why = node.why || why;
    addGhostEdge(edges, current, path, why);
  });
}
