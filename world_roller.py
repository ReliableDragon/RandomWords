"""Pure prompt roller for worldbuilding entries and active pool words."""

from __future__ import annotations

import random
from pathlib import Path


def parse_facets(cheat_sheet: str) -> list[str]:
    """Read the facet list below the Cheat Sheet heading.

    The list ends at the next Markdown heading. Empty lines, headings, and
    blockquote advice are not facets, so editing the source list affects rolls.
    """
    lines = cheat_sheet.splitlines()
    start = next((i + 1 for i, line in enumerate(lines)
                  if line.strip().casefold().lstrip('#').strip() == 'cheat sheet'), None)
    if start is None:
        raise ValueError('Cheat sheet is missing its # Cheat Sheet section.')
    facets = []
    for line in lines[start:]:
        value = line.strip()
        if value.startswith('#'):
            break
        if value and not value.startswith('>'):
            facets.append(value.replace('\\!', '!').replace('\\_', '_'))
    if not facets:
        raise ValueError('Cheat sheet contains no facets.')
    return facets


def load_facets(path: str | Path) -> list[str]:
    """Read the live cheat sheet each time, so edits are immediately used."""
    return parse_facets(Path(path).read_text(encoding='utf-8'))


def _value(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _biome_paths(entry) -> set[str]:
    result = set()
    for biome in _value(entry, 'biomes', ()) or ():
        path = _value(biome, 'path', biome if isinstance(biome, str) else None)
        if path:
            result.add(path)
    return result


def _card(entry) -> dict:
    """Return only stable, JSON-serializable canonical entry fields."""
    return {
        'path': _value(entry, 'path'),
        'title': _value(entry, 'title'),
        'kind': _value(entry, 'kind', ''),
        'folder': _value(entry, 'folder', ''),
        'biomes': sorted(_biome_paths(entry)),
    }


def _entries_map(entries) -> dict[str, object]:
    if isinstance(entries, dict):
        return dict(entries)
    return {_value(entry, 'path'): entry for entry in entries}


def _inbound_count(backlinks, path: str) -> int:
    return len(backlinks.get(path, ()))


def _weighted_entry(paths: list[str], backlinks, rng) -> str:
    # A zero-inbound note has weight 1; each inbound link reduces its odds.
    weights = [1.0 / (1 + _inbound_count(backlinks, path)) for path in paths]
    return rng.choices(paths, weights=weights, k=1)[0]


def roll(entries, backlinks, active_words, cheat_sheet, *, facet=None,
         entry=None, words=None, rng=None) -> dict:
    """Create a prompt from index entries and the currently active word pool.

    ``cheat_sheet`` is either source text or a path to the live How-To file.
    Supplied facet, entry, and words are retained; missing fields are drawn.
    ``entry`` accepts a canonical path or an entry card. Its result is a card,
    or a two-card list for a same-biome interaction.
    """
    rng = rng or random.Random()
    if isinstance(cheat_sheet, Path):
        facets = load_facets(cheat_sheet)
    elif isinstance(cheat_sheet, str) and '\n' not in cheat_sheet and '\r' not in cheat_sheet:
        candidate = Path(cheat_sheet)
        facets = load_facets(candidate) if candidate.is_file() else parse_facets(cheat_sheet)
    else:
        facets = parse_facets(str(cheat_sheet))
    by_path = _entries_map(entries)
    if not by_path:
        raise ValueError('At least one entry is required.')
    active_words = list(active_words)
    if words is None:
        if len(active_words) < 2:
            raise ValueError('The active pool must contain at least two words.')
        chosen_words = rng.sample(active_words, 2)
    else:
        chosen_words = list(words)

    chosen_facet = facet if facet is not None else rng.choice(facets)
    chosen_entry = entry
    if isinstance(chosen_entry, dict):
        selected_paths = [chosen_entry.get('path')]
    elif isinstance(chosen_entry, (list, tuple)):
        selected_paths = [(_value(item, 'path') if not isinstance(item, str) else item)
                          for item in chosen_entry]
    elif isinstance(chosen_entry, str):
        selected_paths = [chosen_entry]
    else:
        selected_paths = []

    if selected_paths:
        missing = [path for path in selected_paths if path not in by_path]
        if missing:
            raise ValueError(f'Unknown canonical entry path: {missing[0]}')
    else:
        paths = sorted(by_path)
        shared_biome_pairs = [
            (left, right)
            for i, left in enumerate(paths)
            for right in paths[i + 1:]
            if _biome_paths(by_path[left]) & _biome_paths(by_path[right])
        ]
        make_interaction = bool(shared_biome_pairs and rng.random() < 0.25)
        if make_interaction:
            selected_paths = list(rng.choice(shared_biome_pairs))
            chosen_facet = facet if facet is not None else 'Interaction'
        else:
            selected_paths = [_weighted_entry(paths, backlinks or {}, rng)]

    cards = [_card(by_path[path]) for path in selected_paths]
    result = {
        'facet': chosen_facet,
        'entry': cards[0] if len(cards) == 1 else cards,
        'words': chosen_words,
    }
    return result
