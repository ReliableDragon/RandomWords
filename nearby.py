"""Phase-one Nearby suggestions."""
from __future__ import annotations

import re
import unicodedata


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _utf16(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _excluded(text: str) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in re.finditer(r"\[\[[^\]]+\]\]", text)]
    header_start = 1 if text.startswith("\ufeff") else 0
    if text.lstrip("\ufeff").startswith("---"):
        match = re.match(r"(?s)^\ufeff?---\s*\n.*?\n---(?:\s*\n|$)", text)
        if match:
            spans.append((match.start(), match.end()))
            header_start = match.end()
    # Entry metadata headers are consecutive at the start of the source
    # (after optional frontmatter), and are not prose mentions.
    cursor = header_start
    while cursor < len(text):
        line_end = text.find("\n", cursor)
        line_end = len(text) if line_end < 0 else line_end + 1
        line = text[cursor:line_end].rstrip("\r\n")
        if not re.match(r"^(?:From|Origin|Source|Themes):\s*", line, re.I):
            break
        spans.append((cursor, line_end))
        cursor = line_end
    spans.extend((m.start(), m.end()) for m in re.finditer(r"(?ms)^```.*?^```\s*$", text))
    return spans


def suggestions(draft, index, client_revision) -> dict[str, list[dict]]:
    """Return grouped, JSON-ready suggestions for a parsed draft Entry."""
    index.ensure_ready()
    groups = {"named_not_linked": [], "same_biome": [], "same_tags": [],
              "talks_about_same_things": [], "linked_from_what_you_link": []}
    excluded = _excluded(draft.raw)
    names: dict[tuple[str, str], None] = {}
    for path, entry in index.entries.items():
        if path == draft.path:
            continue
        for spelling in [entry.title, *entry.aliases]:
            key = _key(spelling)
            candidates = set(index.titles.get(key, ())) | set(index.aliases.get(key, ()))
            if candidates == {path}:
                names[(spelling, path)] = None
    occupied: list[tuple[int, int]] = []
    matches = []
    for (spelling, path) in names:
        for match in re.finditer(r"(?<![\w])" + re.escape(spelling) + r"(?![\w])",
                                 draft.raw, re.I):
            matches.append((match.start(), match.end(), path))
    for start, end, path in sorted(matches, key=lambda m: (m[0], -(m[1] - m[0]))):
        if any(start < b and end > a for a, b in excluded + occupied):
            continue
        expected = draft.raw[start:end]
        if _key(expected) not in index.titles and _key(expected) not in index.aliases:
            continue
        occupied.append((start, end))
        card = index.card(index.entries[path])
        title = index.entries[path].title
        title_paths = index.titles.get(_key(title), ())
        link_target = title if len(title_paths) == 1 else path[:-3]
        card.update({"reason": f"Named as {expected}", "start": _utf16(draft.raw[:start]),
                     "end": _utf16(draft.raw[:end]), "expected": expected,
                     "client_revision": client_revision, "link_target": link_target})
        groups["named_not_linked"].append(card)

    draft_biomes = {m.path for m in index.memberships.get(draft.path, ())}
    direct_places = getattr(index, "direct_places", {})
    draft_direct_places = {
        path for path in direct_places.get(draft.path, ())
        if (path.startswith("Locations/Places/") or
            path.startswith("Locations/Settlements/"))
    }
    # Drafts may not yet exist in the index, so resolve their From targets now.
    if not draft_biomes or not draft_direct_places:
        for link in draft.from_targets:
            resolved = index.resolve(link.target, draft.path)
            if resolved.path:
                if (resolved.path.startswith("Locations/Places/") or
                        resolved.path.startswith("Locations/Settlements/")):
                    draft_direct_places.add(resolved.path)
                if resolved.path.startswith("Locations/Biomes/"):
                    draft_biomes.add(resolved.path)
                draft_biomes.update(m.path for m in index.memberships.get(resolved.path, ()))
    draft_tags = {_key(tag) for tag in draft.tags}
    direct_paths = set()
    for link in draft.links:
        resolved = index.resolve(link.target, draft.path)
        if resolved.path:
            direct_paths.add(resolved.path)
    for path, entry in index.entries.items():
        if path == draft.path:
            continue
        shared_biomes = draft_biomes & {m.path for m in index.memberships.get(path, ())}
        shared_places = draft_direct_places & {
            place for place in direct_places.get(path, ())
            if (place.startswith("Locations/Places/") or
                place.startswith("Locations/Settlements/"))
        }
        if shared_biomes or shared_places:
            reasons = []
            if shared_biomes:
                titles = [index.entries[p].title for p in sorted(shared_biomes)]
                reasons.append("Shared biome: " + ", ".join(titles))
            if shared_places:
                titles = [index.entries[p].title for p in sorted(shared_places)]
                reasons.append("Shared place: " + ", ".join(titles))
            groups["same_biome"].append(
                index.card(entry) |
                {"reason": "; ".join(reasons),
                 "shared_direct_places": sorted(shared_places)}
            )
        shared_tags = draft_tags & {_key(tag) for tag in entry.tags}
        if shared_tags:
            score = len(shared_tags) / len(draft_tags | {_key(tag) for tag in entry.tags})
            groups["same_tags"].append(index.card(entry) |
                                       {"reason": "Shared tags: " + ", ".join(sorted(shared_tags)),
                                        "_score": score})
    groups["same_biome"].sort(key=lambda card: (_key(card["title"]), card["path"]))
    groups["same_tags"].sort(key=lambda card: (-card["_score"], _key(card["title"]), card["path"]))
    for card in groups["same_tags"]:
        del card["_score"]

    for path, score, shared in index.bm25(draft.body):
        if path == draft.path or path in direct_paths:
            continue
        terms = list(shared[:5])
        groups["talks_about_same_things"].append(
            index.card(index.entries[path]) |
            {"reason": "Shared terms: " + ", ".join(terms), "shared_terms": terms}
        )
        if len(groups["talks_about_same_things"]) >= 10:
            break

    two_hop: dict[str, set[str]] = {}
    for intermediate in sorted(direct_paths):
        if intermediate == draft.path or intermediate not in index.entries:
            continue
        for resolved in index.forward_links.get(intermediate, ()):
            candidate = resolved.path
            if not candidate or candidate == draft.path or candidate in direct_paths:
                continue
            two_hop.setdefault(candidate, set()).add(intermediate)
    for path in sorted(two_hop, key=lambda p: (_key(index.entries[p].title), p)):
        intermediate_paths = sorted(two_hop[path],
                                    key=lambda p: (_key(index.entries[p].title), p))
        names = [index.entries[p].title for p in intermediate_paths]
        groups["linked_from_what_you_link"].append(
            index.card(index.entries[path]) |
            {"reason": "Linked from " + ", ".join(names),
             "via": intermediate_paths}
        )
    return groups


nearby = suggestions
