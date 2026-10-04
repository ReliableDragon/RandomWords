"""Phase-one Nearby suggestions."""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

from entry import _WIKILINK, _fenced_block_spans


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _utf16(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _excluded(text: str) -> list[tuple[int, int]]:
    spans = [(match.start(), match.end()) for match in _WIKILINK.finditer(text)]
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
    spans.extend(_fenced_block_spans(text))
    return spans


_WORD_RUN = re.compile(r"\w+")


@lru_cache(maxsize=4096)
def _name_pattern(spelling: str) -> re.Pattern:
    return re.compile(r"(?<![\w])" + re.escape(spelling) + r"(?![\w])", re.I)


class NameMatcher:
    """Finds unambiguous entry names in prose without scanning every name.

    Names are indexed by their first word so one pass over a note's words
    finds the few candidates worth a full match. A name that does not start
    with a word character (``???``) is searched for directly.
    """

    def __init__(self, names):
        self._by_first: dict[str, list[tuple[str, str]]] = {}
        self._other: list[tuple[str, str]] = []
        for spelling, path in names:
            # A name with no letter or digit ("???") is punctuation, not a
            # name that prose can be said to mention.
            if not any(character.isalnum() for character in
                       unicodedata.normalize("NFC", spelling)):
                continue
            first = _WORD_RUN.match(spelling)
            if first:
                self._by_first.setdefault(first.group().lower(), []).append((spelling, path))
            else:
                self._other.append((spelling, path))

    def find(self, raw: str) -> list[tuple[int, int, str]]:
        """Every whole-name, case-insensitive match as ``(start, end, path)``."""
        found = []
        if self._by_first:
            for word in _WORD_RUN.finditer(raw):
                for spelling, path in self._by_first.get(word.group().lower(), ()):
                    match = _name_pattern(spelling).match(raw, word.start())
                    if match:
                        found.append((match.start(), match.end(), path))
        for spelling, path in self._other:
            found.extend((m.start(), m.end(), path)
                         for m in _name_pattern(spelling).finditer(raw))
        return found


def name_matcher(index) -> NameMatcher:
    """A matcher over every title and alias that names exactly one entry."""
    names: dict[tuple[str, str], None] = {}
    for path, entry in index.entries.items():
        for spelling in [entry.title, *entry.aliases]:
            key = _key(spelling)
            candidates = set(index.titles.get(key, ())) | set(index.aliases.get(key, ()))
            if candidates == {path}:
                names[(spelling, path)] = None
    return NameMatcher(names)


def unlinked_mentions(raw: str, index, matcher: NameMatcher,
                      skip_path: str | None = None) -> list[tuple[int, int, str]]:
    """Prose occurrences of entry names that are not linked, as
    ``(start, end, path)`` in Python offsets, ordered by position.

    Existing wikilinks, frontmatter, metadata header lines and fenced code
    are excluded, overlapping matches keep the longest, and the note named by
    ``skip_path`` (the note being scanned) never matches itself.
    """
    excluded = sorted(_excluded(raw))
    matches = [m for m in matcher.find(raw) if m[2] != skip_path]
    excluded_index = 0
    occupied_end = -1
    result = []
    for start, end, path in sorted(matches, key=lambda m: (m[0], -(m[1] - m[0]))):
        while (excluded_index < len(excluded)
               and excluded[excluded_index][1] <= start):
            excluded_index += 1
        if (excluded_index < len(excluded)
                and start < excluded[excluded_index][1]
                and end > excluded[excluded_index][0]):
            continue
        if start < occupied_end:
            continue
        expected = raw[start:end]
        if _key(expected) not in index.titles and _key(expected) not in index.aliases:
            continue
        occupied_end = end
        result.append((start, end, path))
    return result


def link_target(index, path: str) -> str:
    """What to write inside ``[[ ]]`` to reach ``path``: its title when no other
    note has that title or alias, else its path without ``.md``."""
    title = index.entries[path].title
    key = _key(title)
    owners = set(index.titles.get(key, ())) | set(getattr(index, "aliases", {}).get(key, ()))
    return title if owners == {path} else path[:-3]


_link_target = link_target


def _is_place(path: str) -> bool:
    return path.startswith("Locations/")


# How much each reason counts toward a merged card's score.
MERGE_WEIGHTS = {"named_not_linked": 5.0, "same_biome": 2.0, "shared_place": 1.0,
                 "same_tags": 2.0, "talks_about_same_things": 2.0,
                 "linked_from_what_you_link": 1.5}
# A named mention spelled unlike the title or alias ("time" for Time) is
# probably the ordinary word, so it counts for less; it stays linkable.
LOWERCASE_NAMED_WEIGHT = 1.0
MERGED_LIMIT = 25


def suggestions(draft, index, client_revision) -> dict[str, list[dict]]:
    """Return grouped, JSON-ready suggestions for a parsed draft Entry."""
    return _collect(draft, index, client_revision)[0]


def suggest(draft, index, client_revision, suppressed_targets=frozenset()) -> dict:
    """Grouped suggestions plus the ``merged`` one-card-per-entry list.

    Entries in ``suppressed_targets`` (paths) are never offered as
    named-not-linked, in the group or in merged reasons.
    """
    groups, signals = _collect(draft, index, client_revision, suppressed_targets)
    return {"groups": groups, "merged": merge(groups, signals)}


def _collect(draft, index, client_revision, suppressed_targets=frozenset()):
    index.ensure_ready()
    groups = {"named_not_linked": [], "same_biome": [], "same_tags": [],
              "talks_about_same_things": [], "linked_from_what_you_link": []}
    signals = {"same_tags": {}, "talks_about_same_things": {}}
    for start, end, path in unlinked_mentions(draft.raw, index, name_matcher(index),
                                              skip_path=draft.path):
        if path in suppressed_targets:
            continue
        expected = draft.raw[start:end]
        target = index.entries[path]
        card = index.card(target)
        card.update({"reason": f"Named as {expected}", "start": _utf16(draft.raw[:start]),
                     "end": _utf16(draft.raw[:end]), "expected": expected,
                     "exact_case": expected in (target.title, *target.aliases),
                     "client_revision": client_revision,
                     "link_target": _link_target(index, path)})
        groups["named_not_linked"].append(card)

    draft_biomes = {m.path for m in index.memberships.get(draft.path, ())}
    direct_places = getattr(index, "direct_places", {})
    draft_direct_places = {
        path for path in direct_places.get(draft.path, ())
        if path.startswith(("Locations/Places/", "Locations/Settlements/"))
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
            if place.startswith(("Locations/Places/", "Locations/Settlements/"))
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
            signals["same_tags"][path] = (score, sorted(shared_tags))
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
        signals["talks_about_same_things"][path] = score
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
    draft_title = _key(draft.title)
    for cards in groups.values():
        for card in cards:
            card["is_place"] = _is_place(card["path"])
            card["namesake"] = (_key(card["title"]) == draft_title
                                and card["path"] != draft.path)
    return groups, signals


def merge(groups: dict[str, list[dict]], signals: dict) -> list[dict]:
    """Fold the groups into one weighted card per entry.

    Weights: named-not-linked 5, or 1 when only spelled unlike the title or
    alias (keeping its span and link fields, from the first exact-case
    occurrence, so *Link it* works from the merged card), same biome 2
    (+1 when a direct place is shared), same tags 2 x Jaccard, talks about the
    same things 2 x score / best score in that group, linked from what you
    link 1.5. Sorted by score, then title and path; capped at ``MERGED_LIMIT``.
    """
    cards: dict[str, dict] = {}
    scores: dict[str, float] = {}

    def add(card: dict, weight: float, group: str, **fields) -> None:
        path = card["path"]
        if path not in cards:
            cards[path] = {key: card[key] for key in ("path", "title", "folder",
                                                     "is_place", "namesake")}
            scores[path] = 0.0
            cards[path]["reasons"] = []
        scores[path] += weight
        cards[path]["reasons"].append(
            {"group": group, "text": card["reason"], "weight": round(weight, 4), **fields})

    # One reason per entry, from its first exact-case mention if it has one.
    named: dict[str, dict] = {}
    occurrences: dict[str, int] = {}
    for card in groups.get("named_not_linked", ()):
        path = card["path"]
        occurrences[path] = occurrences.get(path, 0) + 1
        best = named.get(path)
        if best is None or (card.get("exact_case", True) and not best.get("exact_case", True)):
            named[path] = card
    for path, card in named.items():
        exact = card.get("exact_case", True)
        fields = {key: card[key] for key in ("start", "end", "expected",
                                             "client_revision", "link_target")}
        text = card["reason"] if exact else f"Named as {card['expected']} (lowercase)"
        add(dict(card, reason=text),
            MERGE_WEIGHTS["named_not_linked"] if exact else LOWERCASE_NAMED_WEIGHT,
            "named_not_linked", occurrences=occurrences[path], exact_case=exact, **fields)
    for card in groups.get("same_biome", ()):
        places = list(card.get("shared_direct_places", ()))
        weight = MERGE_WEIGHTS["same_biome"] + (MERGE_WEIGHTS["shared_place"] if places else 0.0)
        add(card, weight, "same_biome", shared_direct_places=places)
    for card in groups.get("same_tags", ()):
        jaccard, shared = signals.get("same_tags", {}).get(card["path"], (0.0, []))
        add(card, MERGE_WEIGHTS["same_tags"] * jaccard, "same_tags",
            shared_tags=shared, jaccard=round(jaccard, 4))
    talk_scores = signals.get("talks_about_same_things", {})
    best = max((talk_scores.get(card["path"], 0.0)
                for card in groups.get("talks_about_same_things", ())), default=0.0)
    for card in groups.get("talks_about_same_things", ()):
        relative = talk_scores.get(card["path"], 0.0) / best if best else 0.0
        add(card, MERGE_WEIGHTS["talks_about_same_things"] * relative,
            "talks_about_same_things", shared_terms=list(card.get("shared_terms", ())))
    for card in groups.get("linked_from_what_you_link", ()):
        add(card, MERGE_WEIGHTS["linked_from_what_you_link"], "linked_from_what_you_link",
            via=list(card.get("via", ())))
    for path, card in cards.items():
        card["score"] = round(scores[path], 4)
    ranked = sorted(cards.values(),
                    key=lambda card: (-card["score"], _key(card["title"]), card["path"]))
    return ranked[:MERGED_LIMIT]


nearby = suggestions
