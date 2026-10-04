"""Pure prompt roller for worldbuilding entries and active pool words."""

from __future__ import annotations

from collections import Counter
import random
from pathlib import Path

from world_reports import is_world_entry


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


def _card(entry, direct_places=None, link_of=None) -> dict:
    """Return only stable, JSON-serializable canonical entry fields.

    ``biomes`` are the entry's canonical biome paths. ``from_targets`` are the
    canonical paths a new entry started from this roll should name in its
    ``From:`` line: the entry's own direct places (places, settlements and
    biomes it names), or its biomes when it names none.
    """
    biomes = sorted(_biome_paths(entry))
    places = list((direct_places or {}).get(_value(entry, 'path'), ()))
    return {
        'path': _value(entry, 'path'),
        'title': _value(entry, 'title'),
        'kind': _value(entry, 'kind', ''),
        'folder': _value(entry, 'folder', ''),
        'biomes': biomes,
        'from_targets': places or biomes,
        'link': _link(entry, link_of),
    }


def _link(entry, link_of) -> str:
    path = _value(entry, 'path') or ''
    if link_of is not None:
        try:
            return link_of(path)
        except (KeyError, TypeError, ValueError, AttributeError):
            pass
    return path[:-3] if path.endswith('.md') else path


def _entries_map(entries) -> dict[str, object]:
    if isinstance(entries, dict):
        return dict(entries)
    return {_value(entry, 'path'): entry for entry in entries}


def _inbound_count(backlinks, path: str) -> int:
    return len(backlinks.get(path, ()))


# Thin biomes get a mild boost so the world fills in evenly. An entry's bonus
# is 1 + THIN_BIOME_BONUS * (1 - n / N), where n is the number of world
# entries in its thinnest canonical biome and N the number in the fullest
# biome: 1 for the fullest biome (and for entries with no biome), approaching
# 1 + THIN_BIOME_BONUS for a nearly empty one. It multiplies the orphan weight
# rather than replacing it, so unlinked entries still lead.
THIN_BIOME_BONUS = 0.5


def _thin_biome_bonuses(by_path: dict[str, object]) -> dict[str, float]:
    sizes = Counter(biome for entry in by_path.values() for biome in _biome_paths(entry))
    largest = max(sizes.values(), default=0)
    bonuses = {}
    for path, entry in by_path.items():
        biomes = _biome_paths(entry)
        if not biomes or not largest:
            bonuses[path] = 1.0
            continue
        thinnest = min(sizes[biome] for biome in biomes)
        bonuses[path] = 1.0 + THIN_BIOME_BONUS * (1.0 - thinnest / largest)
    return bonuses


def _weighted_entry(paths: list[str], backlinks, rng, bonuses=None) -> str:
    # A zero-inbound note has weight 1; each inbound link reduces its odds.
    bonuses = bonuses or {}
    weights = [bonuses.get(path, 1.0) / (1 + _inbound_count(backlinks, path))
               for path in paths]
    return rng.choices(paths, weights=weights, k=1)[0]


def roll(entries, backlinks, active_words, cheat_sheet, *, facet=None,
         entry=None, words=None, rng=None, direct_places=None,
         link_of=None, story_folders=()) -> dict:
    """Create a prompt from index entries and the currently active word pool.

    ``cheat_sheet`` is either source text or a path to the live How-To file.
    Supplied facet, entry, and words are retained; missing fields are drawn.
    ``entry`` accepts a canonical path or an entry card. Its result is a card,
    or a two-card list for a same-biome interaction. Only world entries are
    drawn at random (not templates, ideas or loose root notes); an entry named
    explicitly is kept whatever it is. ``direct_places`` maps a path to the
    places it names, for each card's ``from_targets``; ``link_of(path)`` gives
    each card's ``link``. Notes under ``story_folders`` are not drawn.
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
        world = {path: item for path, item in by_path.items()
                 if is_world_entry(path, item, story_folders)}
        if not world:
            raise ValueError('At least one world entry is required.')
        paths = sorted(world)
        shared_biome_pairs = [
            (left, right)
            for i, left in enumerate(paths)
            for right in paths[i + 1:]
            if _biome_paths(world[left]) & _biome_paths(world[right])
        ]
        make_interaction = bool(shared_biome_pairs and rng.random() < 0.25)
        if make_interaction:
            selected_paths = list(rng.choice(shared_biome_pairs))
            chosen_facet = facet if facet is not None else 'Interaction'
        else:
            selected_paths = [_weighted_entry(paths, backlinks or {}, rng,
                                              _thin_biome_bonuses(world))]

    cards = [_card(by_path[path], direct_places, link_of) for path in selected_paths]
    result = {
        'facet': chosen_facet,
        'entry': cards[0] if len(cards) == 1 else cards,
        'words': chosen_words,
    }
    return result
