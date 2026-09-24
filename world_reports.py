"""Pure JSON-ready coverage and housekeeping reports for a VaultIndex snapshot."""
from __future__ import annotations

import re

from vault_index import Membership


_ASIDE = re.compile(r"\$\{([^}]*)\}")


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
    biomes = sorted((path for path in entries
                     if path.startswith("Locations/Biomes/")), key=str.casefold)
    kinds = sorted({entry.kind for entry in entries.values()
                    if entry.kind and not _structural(entry.path)
                    and not entry.path.startswith("Ideas/")}, key=str.casefold)
    rows = []
    for biome_path in biomes:
        cells = {}
        for kind in kinds:
            found = []
            for path, entry in entries.items():
                if _structural(path) or path.startswith("Ideas/") or entry.kind != kind:
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
            cells[kind] = {"count": len(found), "entries": found}
        biome = entries[biome_path]
        rows.append({"path": biome_path, "title": biome.title, "cells": cells})
    return {"kinds": kinds, "rows": rows}


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

    unresolved = []
    for path, results in forward_links.items():
        if path not in authored:
            continue
        for position, result in enumerate(results):
            if result.status == "unresolved":
                unresolved.append({"path": path, "title": authored[path].title,
                                   "target": result.target, "link_index": position})

    asides = []
    for path, entry in authored.items():
        for match in _ASIDE.finditer(entry.raw):
            before = entry.raw[:match.start()]
            line = before.count("\n") + 1
            lines = entry.raw.splitlines()
            line_index = line - 1
            start_line = line_index
            while start_line > 0 and lines[start_line - 1].strip():
                start_line -= 1
            end_line = line_index
            while end_line + 1 < len(lines) and lines[end_line + 1].strip():
                end_line += 1
            context = "\n".join(lines[start_line:end_line + 1]).strip()
            asides.append({"path": path, "title": entry.title,
                           "text": match.group(1), "context": context,
                           "line": line})

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
    }


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


def _structural(path: str) -> bool:
    """Exclude only template scaffolding from reports and coverage."""
    return path.startswith("Templates/") or path.startswith(".obsidian/")
