"""Coined-word lexicon and spelling-drift analysis for a vault index."""
from __future__ import annotations

from collections import Counter, defaultdict
import threading
import unicodedata
import weakref

from file_manager import WORD_RE


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
    stems = {word}
    if word.endswith(("'s", "’s")) and len(word) > 2:
        stems.add(word[:-2])
    if word.endswith("ies") and len(word) > 3:
        stems.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 2:
        stems.add(word[:-2])
        # hero/heroes and similar forms.
        stems.add(word[:-1])
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        stems.add(word[:-1])
    return stems


def _ordinary_inflection(left: str, right: str) -> bool:
    return bool(_inflection_stems(left) & _inflection_stems(right))


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
        spellings: dict[str, Counter[str]] = defaultdict(Counter)
        uses: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for path, entry in self.index.entries.items():
            for token in WORD_RE.findall(unicodedata.normalize("NFC", entry.body)):
                if not any(character.isalpha() for character in token):
                    continue
                canonical = _key(token)
                if canonical in dictionary:
                    continue
                spellings[canonical][unicodedata.normalize("NFC", token)] += 1
                uses[canonical][path] += 1

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
                    drift.append({"from": rare, "to": common,
                                  "distance": distance,
                                  "from_count": counts[rare],
                                  "to_count": counts[common],
                                  "from_paths": sorted(uses[rare]),
                                  "to_paths": sorted(uses[common])})
        drift.sort(key=lambda row: (row["distance"], row["from"], row["to"]))
        return {"entries": entries, "drift": drift}


def lexicon(vault_index, library_files, word_index=None, **filters) -> dict:
    """Convenience one-shot API."""
    return WorldLexicon(vault_index, library_files, word_index).query(**filters)
