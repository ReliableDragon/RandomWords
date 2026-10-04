"""Pure JSON-ready coverage and housekeeping reports for a VaultIndex snapshot."""
from __future__ import annotations

from bisect import bisect_left
import unicodedata

from entry import _ASIDE
from nearby import name_matcher, unlinked_mentions as find_unlinked_mentions
from vault_index import Membership
from world_spans import editor_offsets


# Which template under ``Templates/`` starts an entry of each kind. Kinds with
# several equally good templates (Othernatural) have no default.
KIND_TEMPLATES = {
    "Cosmology": "Cosmology", "Cultures": "Culture", "Flora and Fauna": "Creature",
    "Geonomy": "Geonomy", "Locations": "Place", "People": "Person",
    "Phenomena": "Phenomenon",
}
MENTION_CONTEXT_RADIUS = 100


def _story_folders(index) -> tuple[str, ...]:
    return tuple(getattr(index, "story_folders", ()) or ())


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _snapshot(index):
    """Read the already-built snapshot without triggering a vault refresh."""
    return (index.entries, index.memberships, index.backlinks,
            index.forward_links, getattr(index, "direct_places", {}))


def coverage_matrix(index) -> dict:
    """Return canonical biome rows, kind columns, counts and provenance.

    A canonical biome note is included in its own row. Each entry is counted
    once per biome and kind even if multiple From targets reach that biome.
    Structural template notes are excluded from coverage.
    """
    entries, memberships, _, _, direct_places = _snapshot(index)
    story = _story_folders(index)
    region_folders = getattr(index, "region_folders", None)
    region_folders = region_folders() if callable(region_folders) else {}
    biomes = sorted((path for path in entries
                     if path.startswith("Locations/Biomes/")), key=str.casefold)
    kinds = world_kinds(index)
    rows = []
    for biome_path in biomes:
        cells = {}
        for kind in kinds:
            found = []
            for path, entry in entries.items():
                if not is_world_entry(path, entry, story) or entry.kind != kind:
                    continue
                source_memberships = memberships.get(path, ())
                if path == biome_path:
                    source_memberships = (Membership(biome_path, "canonical_biome", path),)
                matching = [m for m in source_memberships if m.path == biome_path]
                if matching:
                    # Index membership generation is path-deduplicated. Keep a
                    # defensive set here so alternate snapshots remain safe.
                    provenance = list({(m.via, m.source_path) for m in matching})
                    provenance.sort(key=lambda p: (p[0], p[1] or ""))
                    found.append({
                        "path": path,
                        "title": entry.title,
                        "kind": entry.kind,
                        "memberships": [{"via": via, "source_path": source}
                                        for via, source in provenance],
                        "direct_places": _direct_place_rows(
                            direct_places.get(path, ()), entries, biome_path,
                            memberships),
                    })
            found.sort(key=lambda row: (row["title"].casefold(), row["path"].casefold()))
            cells[kind] = {"count": len(found), "entries": found,
                           "create": _create_hint(entries, region_folders,
                                                  biome_path, kind)}
        biome = entries[biome_path]
        rows.append({"path": biome_path, "title": biome.title, "cells": cells})
    return {"kinds": kinds, "rows": rows}


def world_kinds(index) -> list[str]:
    """The ordered kinds of world entries: the Coverage columns."""
    entries = index.entries
    story = _story_folders(index)
    return sorted({entry.kind for path, entry in entries.items()
                   if is_world_entry(path, entry, story)}, key=str.casefold)


def placement(index, from_path: str | None = None, kind: str | None = None) -> dict:
    """Where an entry would live, from the place and/or kind a writer picked.

    ``from_path`` must be an existing entry and ``kind`` one of ``world_kinds``
    (the route checks both). A settlement or place resolves to its canonical
    biome to find the region folder, but ``from_target`` stays the place that
    was chosen. ``suggested_kind`` is the most common kind among entries that
    come from the place, and only when a place was given without a kind.
    """
    entries, memberships, _, _, direct_places = _snapshot(index)
    story = _story_folders(index)
    result = {"kinds": world_kinds(index), "folder": None, "from_target": from_path,
              "template": None, "suggested_kind": None}
    biome = None
    if from_path:
        if from_path.startswith("Locations/Biomes/"):
            biome = from_path
        else:
            biome = next((m.path for m in memberships.get(from_path, ())), None)
    if kind:
        region_folders = getattr(index, "region_folders", None)
        region_folders = region_folders() if callable(region_folders) and biome else {}
        hint = _create_hint(entries, region_folders, biome or "", kind)
        result["folder"], result["template"] = hint["folder"], hint["template"]
    elif from_path:
        counts: dict[str, int] = {}
        for path, entry in entries.items():
            if path == from_path or not is_world_entry(path, entry, story):
                continue
            if from_path in direct_places.get(path, ()) or any(
                    m.path == from_path for m in memberships.get(path, ())):
                counts[entry.kind] = counts.get(entry.kind, 0) + 1
        if counts:
            result["suggested_kind"] = min(counts, key=lambda k: (-counts[k], k.casefold()))
    return result


def _create_hint(entries, region_folders, biome_path: str, kind: str) -> dict:
    """Where and how to start an entry of ``kind`` in ``biome_path``.

    ``folder`` is the existing region folder for that biome under
    ``Flora and Fauna`` or ``Cultures`` (the busiest one if several), else the
    kind's top folder; ``from_target`` is the biome; ``template`` is a
    ``Templates/`` note that exists, or null.
    """
    folder = kind
    if kind in ("Flora and Fauna", "Cultures"):
        counts: dict[str, int] = {}
        for path in entries:
            for region, biome in region_folders.items():
                if biome == biome_path and region.startswith(kind + "/") \
                        and path.startswith(region + "/"):
                    counts[region] = counts.get(region, 0) + 1
        if counts:
            folder = min(counts, key=lambda name: (-counts[name], name))
    elif kind == "Locations" and any(p.startswith("Locations/Places/") for p in entries):
        # Biomes are the regions themselves; new locations go in with places.
        folder = "Locations/Places"
    return {"folder": folder, "from_target": biome_path,
            "template": _template_for(entries, kind)}


def _template_for(entries, kind: str) -> str | None:
    name = KIND_TEMPLATES.get(kind)
    if not name:
        return None
    wanted = {_key(name), _key(name + " Template")}
    matches = sorted(path for path in entries
                     if path.startswith("Templates/") and path.count("/") == 1
                     and _key(path[len("Templates/"):].removesuffix(".md")) in wanted)
    return matches[0] if matches else None


class _Paragraphs:
    """The blank-line-delimited paragraph around each of a note's lines."""

    def __init__(self, raw: str):
        self.lines = raw.splitlines()
        filled = [bool(line.strip()) for line in self.lines]
        self.first = list(range(len(filled)))
        for index in range(1, len(filled)):
            if filled[index - 1]:
                self.first[index] = self.first[index - 1]
        self.last = list(range(len(filled)))
        for index in range(len(filled) - 2, -1, -1):
            if filled[index + 1]:
                self.last[index] = self.last[index + 1]
        self._contexts = {}

    def around(self, index: int) -> str:
        bounds = self.first[index], self.last[index]
        if bounds not in self._contexts:
            self._contexts[bounds] = "\n".join(
                self.lines[bounds[0]:bounds[1] + 1]).strip()
        return self._contexts[bounds]


def _aside_rows(path: str, entry) -> list[dict]:
    """One row per ``${...}`` aside, with its line and paragraph."""
    # Lines are counted from the previous aside, and the note is split into
    # paragraphs once, so many asides do not reread the note.
    rows, line, counted, paragraphs = [], 1, 0, None
    for match in _ASIDE.finditer(entry.raw):
        line += entry.raw.count("\n", counted, match.start())
        counted = match.start()
        if paragraphs is None:
            paragraphs = _Paragraphs(entry.raw)
        rows.append({"path": path, "title": entry.title,
                     "text": match.group(1),
                     "context": paragraphs.around(line - 1), "line": line})
    return rows


def health_report(index) -> dict:
    """Return housekeeping findings; every action row carries its source path.

    Structural policy: Markdown notes below ``Templates/`` are scaffolding,
    not authored world entries, so they are omitted from health counts. Other
    notes, including root-level overview pages, remain visible for review.
    """
    entries, _, backlinks, forward_links, _ = _snapshot(index)
    authored = {p: e for p, e in entries.items() if not _structural(p)}
    stubs = [_note_row(e) for e in authored.values() if e.stub]
    rework = [_note_row(e) for e in authored.values()
              if any(tag.casefold() == "rework" for tag in e.tags)]
    def authored_backlinks(path):
        return any(source_path in authored for source_path, _link in backlinks.get(path, ()))

    no_inbound = [_note_row(e) for p, e in authored.items() if not authored_backlinks(p)]
    isolated = []
    for path, entry in authored.items():
        has_outgoing = any(res.path and res.path in authored
                           for res in forward_links.get(path, ()))
        has_inbound = authored_backlinks(path)
        if not has_outgoing and not has_inbound:
            isolated.append(_note_row(entry))

    # The create form offers the source note's own From: targets for review,
    # since a missing entry usually lives where the note that names it does.
    direct_places = getattr(index, "direct_places", {}) or {}
    unresolved = []
    for path, results in forward_links.items():
        if path not in authored:
            continue
        for position, result in enumerate(results):
            if result.status == "unresolved":
                unresolved.append({"path": path, "title": authored[path].title,
                                   "target": result.target, "link_index": position,
                                   "from_targets": list(direct_places.get(path, ()))})

    asides = [row for path, entry in authored.items()
              for row in _aside_rows(path, entry)]

    def order(rows):
        return sorted(rows, key=lambda row: (row["path"].casefold(),
                                             row.get("line", 0),
                                             row.get("target", "").casefold()))

    return {
        "stubs": order(stubs),
        "unresolved_links": order(unresolved),
        "isolated": order(isolated),
        "no_inbound": order(no_inbound),
        "rework": order(rework),
        "notes_to_self": order(asides),
        # Name discovery and spelling drift belong to the later lexicon/Nearby
        # work; explicit empty sections keep the response shape stable.
        "names_without_entry": [],
        "spelling_drift": [],
        "unlinked_mentions": unlinked_mention_rows(index),
        "ambiguous_links": ambiguous_links(index),
        "name_collisions": name_collisions(index),
    }


def unlinked_mention_rows(index) -> list[dict]:
    """Vault-wide unlinked mentions between world entries.

    Uses Nearby's detection and exclusions (existing wikilinks, frontmatter,
    metadata header lines and fenced code are skipped; overlapping names keep
    the longest; unambiguous titles and aliases only). ``start``/``end`` are
    UTF-16 code units in the editor's text (the source with ``\\n`` newlines,
    see ``world_spans``). ``already_linked`` says the source links the target
    somewhere else; ``exact_case`` says the text is spelled exactly like the
    title or an alias; ``actionable`` is ``exact_case and not already_linked``.
    """
    entries, _, _, forward_links, _ = _snapshot(index)
    story = _story_folders(index)
    matcher = name_matcher(index)
    rows = []
    for path in sorted(entries):
        source = entries[path]
        if not is_world_entry(path, source, story):
            continue
        linked = {res.path for res in forward_links.get(path, ()) if res.path}
        raw = source.raw
        mentions = find_unlinked_mentions(raw, index, matcher, skip_path=path)
        if not mentions:
            continue
        offset = editor_offsets(raw)
        newlines = [position for position, character in enumerate(raw)
                    if character == "\n"]
        for start, end, target in mentions:
            if not is_world_entry(target, entries[target], story):
                continue
            line_index = bisect_left(newlines, start)
            line_start = newlines[line_index - 1] + 1 if line_index else 0
            after_index = bisect_left(newlines, end)
            line_end = (newlines[after_index]
                        if after_index < len(newlines) else len(raw))
            left = max(line_start, start - MENTION_CONTEXT_RADIUS)
            right = min(line_end, end + MENTION_CONTEXT_RADIUS)
            context = (("…" if left > line_start else "") + raw[left:right].strip()
                       + ("…" if right < line_end else ""))
            rows.append({
                "path": path,
                "source_path": path, "source_title": source.title,
                "target_path": target, "target_title": entries[target].title,
                "text": raw[start:end],
                "start": offset(start), "end": offset(end),
                "line": line_index + 1,
                "context": context,
                "source_revision": source.revision,
                "already_linked": target in linked,
                # False for a lower-cased common word that happens to be a
                # title ("time" for Time); the UI may demote such rows.
                "exact_case": raw[start:end] in (entries[target].title,
                                                 *entries[target].aliases),
            })
            rows[-1]["actionable"] = (rows[-1]["exact_case"]
                                      and not rows[-1]["already_linked"])
    return rows


def mention_counts(rows: list[dict]) -> list[dict]:
    """Per-target totals over the actionable unlinked-mention rows: how many
    notes name each target. Rows already linked, or not spelled like the
    title, are left out."""
    totals: dict[str, dict] = {}
    for row in rows:
        if not row.get("actionable", True):
            continue
        total = totals.setdefault(row["target_path"], {
            "target_path": row["target_path"], "target_title": row["target_title"],
            "notes": 0, "mentions": 0, "_sources": set()})
        total["mentions"] += 1
        total["_sources"].add(row["source_path"])
    result = []
    for total in totals.values():
        total["notes"] = len(total.pop("_sources"))
        result.append(total)
    return sorted(result, key=lambda row: (-row["notes"], -row["mentions"],
                                           row["target_title"].casefold(),
                                           row["target_path"]))


def ambiguous_links(index) -> list[dict]:
    """Links whose target text matches more than one note."""
    entries, _, _, forward_links, _ = _snapshot(index)
    rows = []
    for path, results in forward_links.items():
        if path not in entries or _structural(path):
            continue
        for position, result in enumerate(results):
            if result.status == "ambiguous":
                candidates = list(result.candidates)
                rows.append({
                    "path": path, "source_path": path, "title": entries[path].title,
                    "target": result.target, "link_index": position,
                    "candidates": candidates,
                    "candidate_titles": [entries[c].title if c in entries else c
                                         for c in candidates],
                })
    return sorted(rows, key=lambda row: (row["path"].casefold(), row["link_index"]))


def name_collisions(index) -> list[dict]:
    """Titles and aliases shared by several notes, and colliding path spellings."""
    entries = index.entries
    found: dict[tuple[str, str], tuple[str, ...]] = {}
    for name, paths in getattr(index, "collisions", ()):
        kind = "path" if name.startswith("path:") else "name"
        found[(kind, name.removeprefix("path:"))] = tuple(paths)
    titles, aliases = index.titles, getattr(index, "aliases", {})
    for name in set(titles) | set(aliases):
        paths = tuple(sorted(set(titles.get(name, ())) | set(aliases.get(name, ()))))
        if len(paths) > 1:
            found.setdefault(("name", name), paths)
    rows = []
    for (kind, name), paths in found.items():
        if all(_structural(p) for p in paths):
            continue
        members, shown = [], name
        for path in paths:
            entry = entries.get(path)
            via = "title" if entry and _key(entry.title) == name else "alias"
            if entry and kind == "name":
                spelling = entry.title if via == "title" else next(
                    (a for a in entry.aliases if _key(a) == name), name)
                if not members:
                    shown = spelling
            members.append({"path": path, "title": entry.title if entry else path,
                            "via": via if kind == "name" else "path"})
        if kind == "path":
            shown = paths[0]
        rows.append({"name": shown, "kind": kind, "path": paths[0],
                     "paths": list(paths), "entries": members})
    return sorted(rows, key=lambda row: (row["kind"], row["name"].casefold(), row["path"]))


def _note_row(entry):
    return {"path": entry.path, "title": entry.title, "words": entry.words}


def _direct_place_rows(records, entries, biome_path, memberships):
    """Normalize optional direct-place snapshot rows across index revisions."""
    rows = []
    seen = set()
    for record in records:
        if isinstance(record, str):
            path = record
            title = None
        elif isinstance(record, dict):
            path = record.get("path") or record.get("source_path")
            title = record.get("title")
        else:
            path = getattr(record, "path", None) or getattr(record, "source_path", None)
            title = getattr(record, "title", None)
        if (not path or path in seen or
                (path != biome_path and not any(m.path == biome_path
                                                for m in memberships.get(path, ())))):
            continue
        seen.add(path)
        entry = entries.get(path)
        rows.append({"path": path, "title": title or (entry.title if entry else path)})
    return sorted(rows, key=lambda row: (row["title"].casefold(), row["path"].casefold()))


def is_world_entry(path: str, entry, story_folders=()) -> bool:
    """Whether a note describes the world rather than the vault's scaffolding.

    Templates, the Ideas backlog and loose root notes have no kind of their
    own; coverage and the atlas leave them out, and so are the scenes under a
    configured story folder (``story_folders``): they are fiction about the
    world, not entries of it.
    """
    kind = entry.get("kind") if isinstance(entry, dict) else entry.kind
    return (bool(kind) and not _structural(path) and not path.startswith("Ideas/")
            and not any(path.startswith(folder + "/") for folder in story_folders))


def _structural(path: str) -> bool:
    """Exclude only template scaffolding from reports and coverage."""
    return path.startswith(("Templates/", ".obsidian/"))
