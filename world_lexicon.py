"""Coined-word lexicon and spelling-drift analysis for a vault index."""
from __future__ import annotations

from collections import Counter, defaultdict
import re
import threading
import unicodedata
import weakref

from world_spans import editor_offset as _editor_offset

# WORD_RE intentionally stays simple for corpus tokenization. Here combining
# marks must stay attached so NFC-equivalent spellings share one lexicon row
# without losing source offsets needed by the editor.
_LEXICON_WORD_RE = re.compile(
    r"[^\W_](?:[^\W_]|[\u0300-\u036f])*(?:['’][^\W_](?:[^\W_]|[\u0300-\u036f])*)*",
    re.UNICODE,
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


_dictionary_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_dictionary_lock = threading.Lock()


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _dictionary(file_manager) -> frozenset[str]:
    with _dictionary_lock:
        cached = _dictionary_cache.get(file_manager)
        if cached is None:
            cached = frozenset(_key(word) for word in
                               file_manager.get_words("dicts/450k_words.txt"))
            _dictionary_cache[file_manager] = cached
        return cached


def _distance(left: str, right: str, maximum: int = 2) -> int:
    """Bounded Levenshtein distance, returning maximum + 1 when farther."""
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for row, right_char in enumerate(right, 1):
        current = [row]
        floor = current[0]
        for column, left_char in enumerate(left, 1):
            value = min(current[-1] + 1, previous[column] + 1,
                        previous[column - 1] + (left_char != right_char))
            current.append(value)
            floor = min(floor, value)
        if floor > maximum:
            return maximum + 1
        previous = current
    return previous[-1]


def _inflection_stems(word: str) -> set[str]:
    """Return conservative English inflection candidates, including *word*."""
    stems = {word}
    if word.endswith(("'s", "’s")) and len(word) > 3:
        stems.add(word[:-2])
    if word.endswith("ies") and len(word) > 4:
        stems.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 4:
        stems.add(word[:-2])
        # hero/heroes and similar forms.
        stems.add(word[:-1])
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        stems.add(word[:-1])
    if word.endswith("ied") and len(word) > 4:
        stems.add(word[:-3] + "y")
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        stems.add(stem)
        stems.add(stem + "e")
        if len(stem) > 3 and stem[-1:] == stem[-2:-1]:
            stems.add(stem[:-1])
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        stems.add(stem)
        stems.add(stem + "e")
        if len(stem) > 3 and stem[-1:] == stem[-2:-1]:
            stems.add(stem[:-1])
    return stems


def _ordinary_inflection(left: str, right: str) -> bool:
    return bool(_inflection_stems(left) & _inflection_stems(right))


def _coinage_key(word: str, observed_words: set[str]) -> str:
    """Group a novel inflection with its separately observed base spelling."""
    candidates = _inflection_stems(word) - {word}
    bases = sorted(candidate for candidate in candidates
                   if candidate in observed_words)
    return bases[0] if bases else word


def _replacement_for_inflection(spelling: str, source: str,
                                replacement: str) -> str:
    """Keep a possessive or regular plural suffix when staging a correction."""
    folded = _key(spelling)
    suffix = ""
    if folded.endswith(("'s", "’s")) and folded[:-2] == source:
        suffix = spelling[-2:]
    elif folded.endswith("s") and folded[:-1] == source:
        suffix = spelling[-1:]
    return _match_case(spelling[:-len(suffix)] if suffix else spelling,
                       replacement) + suffix




def _occurrence_context(text: str, start: int, end: int,
                        radius: int = 60) -> tuple[str, str]:
    """Return compact same-line context around an exact token span."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    before = text[max(line_start, start - radius):start].lstrip("\r")
    after = text[end:min(line_end, end + radius)].rstrip("\r")
    if start - radius > line_start:
        before = "…" + before
    if end + radius < line_end:
        after += "…"
    return before, after


def _match_case(source: str, replacement: str) -> str:
    """Carry the common casing style of an occurrence to its suggestion."""
    letters = "".join(character for character in source if character.isalpha())
    if letters and letters.isupper():
        return replacement.upper()
    if letters and letters.islower():
        return replacement.lower()
    if source[:1].isupper() and source[1:].islower():
        return replacement[:1].upper() + replacement[1:].lower()
    return replacement


class WorldLexicon:
    """Build JSON-ready coinage and spelling-drift views.

    ``vault_index`` supplies parsed entries and canonical biome membership.
    ``library_files`` supplies the dictionary. ``word_index`` is optional and
    adds library ``which`` results.
    """

    def __init__(self, vault_index, library_files, word_index=None):
        self.index = vault_index
        self.library_files = library_files
        self.word_index = word_index
        self._which_ready = False
        self._which_lock = threading.Lock()

    def _ensure_which(self) -> None:
        if self.word_index is None or self._which_ready:
            return
        with self._which_lock:
            if not self._which_ready:
                self.word_index.ensure_ready()
                self._which_ready = True

    def query(self, q: str = "", biome: str | None = None,
              once: bool = False) -> dict:
        self.index.ensure_ready()
        dictionary = _dictionary(self.library_files)
        raw_spellings: dict[str, Counter[str]] = defaultdict(Counter)
        raw_uses: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        raw_occurrences: dict[str, list[dict]] = defaultdict(list)

        for path, entry in self.index.entries.items():
            body_offset = len(entry.raw) - len(entry.body)
            url_spans = [match.span() for match in _URL_RE.finditer(entry.body)]
            for match in _LEXICON_WORD_RE.finditer(entry.body):
                token = unicodedata.normalize("NFC", match.group())
                if (not any(character.isalpha() for character in token)
                        or any(character.isdigit() for character in token)
                        or any(start < match.end() and match.start() < end
                               for start, end in url_spans)):
                    continue
                canonical = _key(token)
                if any(stem in dictionary for stem in _inflection_stems(canonical)):
                    continue
                raw_spellings[canonical][token] += 1
                raw_uses[canonical][path] += 1
                start = body_offset + match.start()
                end = body_offset + match.end()
                line = entry.raw.count("\n", 0, start) + 1
                context_before, context_after = _occurrence_context(
                    entry.raw, start, end)
                raw_occurrences[canonical].append({
                    "path": path, "revision": entry.revision,
                    "spelling": match.group(), "line": line,
                    "context_before": context_before,
                    "context_after": context_after,
                    "start": _editor_offset(entry.raw, start),
                    "end": _editor_offset(entry.raw, end),
                })

        # A novel base and its possessive/plural variants are one coinage,
        # while the original spellings and occurrence offsets remain intact.
        observed_words = set(raw_spellings)
        spellings: dict[str, Counter[str]] = defaultdict(Counter)
        uses: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        occurrences: dict[str, list[dict]] = defaultdict(list)
        for word, variants in raw_spellings.items():
            canonical = _coinage_key(word, observed_words)
            spellings[canonical].update(variants)
            for path, count in raw_uses[word].items():
                uses[canonical][path] += count
            occurrences[canonical].extend(raw_occurrences[word])

        self._ensure_which()

        needle = _key(q.strip())
        entries = []
        selected = set()
        for word in sorted(spellings):
            word_uses = uses[word]
            if once and len(word_uses) != 1:
                continue
            if needle and needle not in word and not any(
                    needle in _key(spelling) for spelling in spellings[word]):
                continue
            if biome and not any(
                    biome in {membership.path for membership in
                              self.index.memberships.get(path, ())}
                    for path in word_uses):
                continue
            selected.add(word)
            use_rows = []
            for path in sorted(word_uses):
                use_rows.append({
                    "path": path,
                    "count": word_uses[path],
                    "biomes": [membership.path for membership in
                               self.index.memberships.get(path, ())],
                })
            row = {
                "word": word,
                "spellings": [{"spelling": spelling, "count": count}
                              for spelling, count in sorted(
                                  spellings[word].items(),
                                  key=lambda item: (-item[1], _key(item[0]), item[0]))],
                "count": sum(spellings[word].values()),
                "uses": use_rows,
            }
            if self.word_index is not None:
                texts = list(self.word_index.texts_for(word))
                row["which"] = {"count": self.word_index.doc_count(word),
                                "texts": texts}
            entries.append(row)

        drift = []
        words = sorted(spellings)
        counts = {word: sum(spellings[word].values()) for word in words}
        for rare in words:
            # Codes and measurements remain useful lexicon rows, but their
            # digit substitutions are not evidence of spelling drift.
            if any(character.isdigit() for character in rare):
                continue
            for common in words:
                if any(character.isdigit() for character in common):
                    continue
                # Equal-frequency variants have no evidence for a correction
                # direction, so report neither direction.
                if counts[rare] >= counts[common]:
                    continue
                if _ordinary_inflection(rare, common):
                    continue
                distance = _distance(rare, common)
                if distance <= 2 and (rare in selected or common in selected):
                    rare_occurrences = [
                        {**occurrence,
                         "replacement": _replacement_for_inflection(
                             occurrence["spelling"], rare, common)}
                        for occurrence in occurrences[rare]
                    ]
                    drift.append({"from": rare, "to": common,
                                  "distance": distance,
                                  "from_count": counts[rare],
                                  "to_count": counts[common],
                                  "from_paths": sorted(uses[rare]),
                                  "to_paths": sorted(uses[common]),
                                  "occurrences": rare_occurrences})
        drift.sort(key=lambda row: (row["distance"], row["from"], row["to"]))
        return {"entries": entries, "drift": drift}


def lexicon(vault_index, library_files, word_index=None, **filters) -> dict:
    """Convenience one-shot API."""
    return WorldLexicon(vault_index, library_files, word_index).query(**filters)
