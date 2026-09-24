"""In-memory index for a Markdown worldbuilding vault."""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import math
import os
import re
import threading
import time
import unicodedata

from entry import Entry, Link, parse
from vault import UnreadableSource


DEFAULT_FOLDER_BIOMES = {"Bitters": "Bitter Return Mountains"}

# Deliberately grammatical rather than topical. Corpus frequency handles
# ordinary world words; terms such as water, forest, glass and medicine must
# remain available as useful connective tissue.
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "for", "from", "had", "has", "have", "he", "her", "his", "i", "in",
    "is", "it", "its", "not", "of", "on", "or", "she", "that", "the",
    "their", "them", "they", "this", "to", "was", "were", "which", "who",
    "with", "you",
})
_TERM = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_FENCE = re.compile(r"(?ms)^```.*?^```\s*$")


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


@dataclass(frozen=True)
class Resolution:
    target: str
    status: str
    path: str | None = None
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class Membership:
    path: str
    via: str
    source_path: str | None = None


class VaultIndex:
    """A lazily rebuilt, atomically swapped view of a :class:`VaultManager`."""

    def __init__(self, vault, stat_interval: float = 1.0,
                 folder_biomes: dict[str, str] | None = None,
                 story_folders: tuple[str, ...] | list[str] | None = None):
        self.vault = vault
        self.stat_interval = stat_interval
        mappings = DEFAULT_FOLDER_BIOMES if folder_biomes is None else folder_biomes
        self.folder_biomes = {_key(k): v for k, v in mappings.items()}
        from world_story import story_folders as normalize_story_folders
        self.story_folders = normalize_story_folders(story_folders)
        self._lock = threading.RLock()
        self._build_lock = threading.Lock()
        self._last_stat = 0.0
        self._stamps: dict[str, tuple[int, int]] = {}
        self.ready = False
        self.entries: dict[str, Entry] = {}
        self.titles: dict[str, tuple[str, ...]] = {}
        self.aliases: dict[str, tuple[str, ...]] = {}
        self.collisions: list[tuple[str, tuple[str, ...]]] = []
        self.forward_links: dict[str, tuple[Resolution, ...]] = {}
        self.backlinks: dict[str, tuple[tuple[str, Link], ...]] = {}
        self.memberships: dict[str, tuple[Membership, ...]] = {}
        self.direct_places: dict[str, tuple[str, ...]] = {}
        self.tags: dict[str, tuple[str, ...]] = {}
        self.term_frequencies: dict[str, Counter[str]] = {}
        self.document_lengths: dict[str, int] = {}
        self.document_frequencies: dict[str, int] = {}
        self.average_document_length = 0.0

    def ensure_ready(self) -> bool:
        now = time.monotonic()
        with self._lock:
            should_stat = not self.ready or now - self._last_stat >= self.stat_interval
            current = self._stamps
        if not should_stat:
            return True
        with self._build_lock:
            now = time.monotonic()
            with self._lock:
                should_stat = not self.ready or now - self._last_stat >= self.stat_interval
            if not should_stat:
                return True
            stamps = self.vault.stat_all()
            with self._lock:
                self._last_stat = now
                stale = not self.ready or stamps != self._stamps
            if stale:
                self.build(stamps)
        return True

    def build(self, stamps: dict[str, tuple[int, int]] | None = None) -> int:
        stamps = self.vault.stat_all() if stamps is None else stamps
        entries: dict[str, Entry] = {}
        for path in sorted(stamps):
            try:
                text, revision = self.vault.read(path)
            except (OSError, UnicodeError, UnreadableSource):
                continue
            entries[path] = parse(text, path, revision)

        titles = self._multimap((entry.title, path) for path, entry in entries.items())
        aliases = self._multimap((alias, path) for path, entry in entries.items()
                                 for alias in entry.aliases)
        all_names = set(titles) | set(aliases)
        collisions = [(name, tuple(sorted(set(titles.get(name, ())) |
                                          set(aliases.get(name, ())))))
                      for name in all_names
                      if len(set(titles.get(name, ())) | set(aliases.get(name, ()))) > 1]
        path_keys: dict[str, list[str]] = {}
        for path in entries:
            path_keys.setdefault(_key(path), []).append(path)
        collisions.extend(("path:" + name, tuple(sorted(paths)))
                          for name, paths in path_keys.items() if len(paths) > 1)

        def resolve(target: str, source_path: str | None = None) -> Resolution:
            return self._resolve_in(target, source_path, entries, titles, aliases)

        forward: dict[str, tuple[Resolution, ...]] = {}
        backlink_work: dict[str, list[tuple[str, Link]]] = {}
        for path, entry in entries.items():
            resolved = []
            for link in entry.links:
                result = resolve(link.target, path)
                resolved.append(result)
                if result.path:
                    backlink_work.setdefault(result.path, []).append((path, link))
            forward[path] = tuple(resolved)

        biome_paths = {p for p in entries if p.startswith("Locations/Biomes/")}
        memberships: dict[str, tuple[Membership, ...]] = {}
        direct_places: dict[str, tuple[str, ...]] = {}
        for path, entry in entries.items():
            found: list[Membership] = []
            seen: set[str] = set()
            immediate: list[str] = []

            def add(candidate: str, via: str, source: str | None):
                if candidate in biome_paths and candidate not in seen:
                    seen.add(candidate)
                    found.append(Membership(candidate, via, source))

            def ancestry(candidate: str, root: bool, visiting: set[str], source: str):
                if candidate in visiting:
                    return
                if candidate in biome_paths:
                    add(candidate, "from_target" if root else "ancestor_target", source)
                    return
                parent = entries.get(candidate)
                if not parent:
                    return
                visiting = visiting | {candidate}
                for parent_link in parent.from_targets:
                    r = resolve(parent_link.target, candidate)
                    if r.path:
                        ancestry(r.path, False, visiting, source)

            for link in entry.from_targets:
                r = resolve(link.target, path)
                if r.path:
                    if (r.path.startswith("Locations/Places/") or
                            r.path.startswith("Locations/Settlements/") or
                            r.path.startswith("Locations/Biomes/")):
                        if r.path not in immediate:
                            immediate.append(r.path)
                    ancestry(r.path, True, {path}, r.path)

            region = self._taxonomy_region(path)
            if region:
                mapped = self.folder_biomes.get(_key(region), region)
                explicit = mapped if mapped.casefold().endswith(".md") else mapped + ".md"
                candidates = {p for p in biome_paths if _key(p) == _key(explicit)}
                name = _key(mapped.rsplit("/", 1)[-1].removesuffix(".md"))
                candidates.update(p for p in titles.get(name, ()) if p in biome_paths)
                candidates.update(p for p in aliases.get(name, ()) if p in biome_paths)
                if len(candidates) == 1:
                    add(next(iter(candidates)), "folder_fallback", region)
            memberships[path] = tuple(found)
            direct_places[path] = tuple(immediate)
            # Keep the parsed object convenient for route serialization.
            entry.biomes = list(found)

        tag_work: dict[str, list[str]] = {}
        for path, entry in entries.items():
            for tag in entry.tags:
                tag_work.setdefault(_key(tag), []).append(path)

        term_frequencies: dict[str, Counter[str]] = {}
        document_lengths: dict[str, int] = {}
        document_frequencies: Counter[str] = Counter()
        for path, entry in entries.items():
            frequencies = Counter(self.terms(entry.body))
            term_frequencies[path] = frequencies
            document_lengths[path] = sum(frequencies.values())
            document_frequencies.update(frequencies)
        average_document_length = (
            sum(document_lengths.values()) / len(document_lengths)
            if document_lengths else 0.0
        )

        with self._lock:
            self.entries = entries
            self.titles = titles
            self.aliases = aliases
            self.collisions = sorted(collisions)
            self.forward_links = forward
            self.backlinks = {p: tuple(v) for p, v in backlink_work.items()}
            self.memberships = memberships
            self.direct_places = direct_places
            self.tags = {tag: tuple(paths) for tag, paths in tag_work.items()}
            self.term_frequencies = term_frequencies
            self.document_lengths = document_lengths
            self.document_frequencies = dict(document_frequencies)
            self.average_document_length = average_document_length
            self._stamps = dict(stamps)
            self.ready = True
        return len(entries)

    @staticmethod
    def terms(body: str) -> list[str]:
        """Unicode body terms, excluding fenced code and grammar stop words."""
        body = _FENCE.sub(" ", body)
        return [term for match in _TERM.finditer(body)
                if (term := _key(match.group())) not in STOP_WORDS]

    def bm25(self, text: str, limit: int | None = None) -> list[tuple[str, float, tuple[str, ...]]]:
        """Rank indexed entries against body text with positive BM25 IDF.

        Results contain ``(path, score, shared_terms)`` and are stable for
        equal scores. Repeated query terms contribute their actual frequency.
        """
        self.ensure_ready()
        query = Counter(self.terms(text))
        if not query:
            return []
        with self._lock:
            count = len(self.entries)
            average = self.average_document_length or 1.0
            rows = []
            for path, frequencies in self.term_frequencies.items():
                shared = tuple(sorted(query.keys() & frequencies.keys(),
                                      key=lambda term: (-query[term] * frequencies[term], term)))
                if not shared:
                    continue
                length = self.document_lengths[path]
                score = 0.0
                for term in shared:
                    frequency = frequencies[term]
                    documents = self.document_frequencies[term]
                    idf = math.log(1.0 + (count - documents + 0.5) / (documents + 0.5))
                    norm = frequency + 1.2 * (1.0 - 0.75 + 0.75 * length / average)
                    score += query[term] * idf * frequency * 2.2 / norm
                rows.append((path, score, shared))
            rows.sort(key=lambda row: (-row[1], _key(self.entries[row[0]].title), row[0]))
            return rows if limit is None else rows[:limit]

    @staticmethod
    def _multimap(items) -> dict[str, tuple[str, ...]]:
        work: dict[str, list[str]] = {}
        for name, path in items:
            work.setdefault(_key(name), []).append(path)
        return {name: tuple(sorted(set(paths))) for name, paths in work.items()}

    @staticmethod
    def _resolve_in(target, source_path, entries, titles, aliases) -> Resolution:
        raw = target.strip().replace("\\", "/")
        path_target = raw if raw.casefold().endswith(".md") else raw + ".md"
        # A slash denotes an explicit vault-relative path. Exact canonical
        # paths also work with a supplied .md suffix.
        explicit = next((p for p in entries if _key(p) == _key(path_target)), None)
        if explicit and ("/" in raw or raw.casefold().endswith(".md")):
            return Resolution(target, "resolved", explicit)
        if source_path:
            folder = source_path.rpartition("/")[0]
            local = (folder + "/" if folder else "") + path_target.rsplit("/", 1)[-1]
            local_match = next((p for p in entries if _key(p) == _key(local)), None)
            if local_match:
                return Resolution(target, "resolved", local_match)
        candidates = tuple(sorted(set(titles.get(_key(raw), ())) |
                                  set(aliases.get(_key(raw), ()))))
        if len(candidates) == 1:
            return Resolution(target, "resolved", candidates[0])
        if candidates:
            return Resolution(target, "ambiguous", candidates=candidates)
        return Resolution(target, "unresolved")

    def resolve(self, target: str, source_path: str | None = None) -> Resolution:
        self.ensure_ready()
        with self._lock:
            return self._resolve_in(target, source_path, self.entries,
                                    self.titles, self.aliases)

    def entry(self, path: str) -> Entry | None:
        self.ensure_ready()
        with self._lock:
            return self.entries.get(path)

    def get_backlinks(self, path: str) -> list[dict]:
        """Backlinks with source identity and the exact source link context."""
        self.ensure_ready()
        with self._lock:
            rows = []
            for source_path, link in self.backlinks.get(path, ()):
                source = self.entries[source_path]
                rows.append({"path": source_path, "title": source.title,
                             "folder": source.folder, "target": link.target,
                             "display": link.display,
                             "span": ({"start": link.span.start, "end": link.span.end}
                                      if link.span else None)})
            return rows

    def search(self, query: str, limit: int = 50) -> list[dict]:
        self.ensure_ready()
        needle = _key(query.strip())
        with self._lock:
            ranked = []
            for path, entry in self.entries.items():
                names = [entry.title, *entry.aliases]
                name_match = min((_key(n).find(needle) for n in names if needle in _key(n)), default=-1)
                body_match = needle and needle in _key(entry.body)
                if name_match >= 0 or body_match:
                    ranked.append((0 if name_match >= 0 else 1, name_match, _key(entry.title), path, entry))
            ranked.sort(key=lambda row: row[:4])
            return [self.card(row[4]) | {"kind": row[4].kind, "words": row[4].words,
                                         "stub": row[4].stub, "aliases": list(row[4].aliases)}
                    for row in ranked[:limit]]

    def tree(self, folder: str = "") -> list[dict]:
        self.ensure_ready()
        prefix = folder.rstrip("/") + "/" if folder else ""
        result: dict[str, dict] = {}
        with self._lock:
            for path, entry in self.entries.items():
                if not path.startswith(prefix):
                    continue
                rest = path[len(prefix):]
                head, slash, _ = rest.partition("/")
                if slash:
                    child = prefix + head
                    result[child] = {"path": child, "name": head, "type": "folder"}
                else:
                    result[path] = self.card(entry) | {"name": entry.title, "type": "note",
                                                               "words": entry.words, "stub": entry.stub}
        return sorted(result.values(), key=lambda x: (x["type"] != "folder", _key(x["name"])))

    @staticmethod
    def card(entry: Entry) -> dict:
        return {"path": entry.path, "title": entry.title, "folder": entry.folder}

    @staticmethod
    def _taxonomy_region(path: str) -> str | None:
        parts = path.split("/")
        if len(parts) >= 4 and parts[0] == "Flora and Fauna":
            return parts[2]
        if len(parts) >= 3 and parts[0] == "Cultures":
            return parts[1]
        return None
