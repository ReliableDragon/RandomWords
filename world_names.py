"""Conservative report of capitalized prose names without vault entries."""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

from file_manager import WORD_RE


_WIKILINK = re.compile(r"\[\[[^\]]+\]\]")
_FENCE = re.compile(r"(?ms)^```.*?^```\s*$")
_TAG = re.compile(r"(?<![\w])#[\w-]+", re.UNICODE)
_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+.*$")
_COMMON_SINGLE = frozenset({
    "a", "add", "after", "again", "all", "also", "although", "an", "and", "as",
    "at", "because", "before", "but", "by", "during", "each", "even",
    "every", "finally", "first", "for", "from", "he", "her", "here",
    "however", "i", "if", "in", "instead", "it", "later", "many", "most",
    "no", "now", "often", "on", "once", "one", "or", "other", "our",
    "she", "since", "some", "sometimes", "still", "that", "the", "their",
    "then", "there", "these", "they", "this", "those", "though", "to",
    "until", "we", "when", "where", "while", "with", "yet", "you",
})
_CONNECTOR_PREFIX = _COMMON_SINGLE - {"a", "an", "the"}
_ROOT_REFERENCE_NOTES = frozenset({
    "How-To.md", "Overview.md", "Questions.md", "Sandbox.md", "Tags.md",
})


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _utf16(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _metadata_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    cursor = 1 if text.startswith("\ufeff") else 0
    if text.lstrip("\ufeff").startswith("---"):
        frontmatter = re.match(r"(?s)^\ufeff?---\s*\n.*?\n---(?:\s*\n|$)", text)
        if frontmatter:
            spans.append((frontmatter.start(), frontmatter.end()))
            cursor = frontmatter.end()
    while cursor < len(text):
        line_end = text.find("\n", cursor)
        line_end = len(text) if line_end < 0 else line_end + 1
        line = text[cursor:line_end].rstrip("\r\n")
        if not re.match(r"^(?:From|Origin|Source|Themes):\s*", line, re.I):
            break
        spans.append((cursor, line_end))
        cursor = line_end
    return spans


def _masked(text: str) -> str:
    chars = list(text)
    spans = _metadata_spans(text)
    for pattern in (_WIKILINK, _FENCE, _TAG, _HEADING):
        spans.extend((match.start(), match.end()) for match in pattern.finditer(text))
    for start, end in spans:
        for offset in range(start, end):
            if chars[offset] not in "\r\n":
                chars[offset] = " "
    return "".join(chars)


def _proper(token: str) -> bool:
    if any(character.isdigit() for character in token):
        return False
    letters = [character for character in token if character.isalpha()]
    return bool(letters and letters[0].isupper() and any(c.islower() for c in letters))


def _sentence_start(text: str, start: int) -> bool:
    prefix = text[:start].rstrip()
    return not prefix or prefix[-1] in ".!?" or "\n" in text[len(prefix):start]


def _occurrences(text: str) -> list[dict]:
    masked = _masked(text)
    tokens = [match for match in WORD_RE.finditer(masked) if _proper(match.group())]
    runs = []
    index = 0
    while index < len(tokens):
        run = [tokens[index]]
        following = index + 1
        while following < len(tokens):
            between = masked[run[-1].end():tokens[following].start()]
            # A name may contain spaces or tabs, but cannot cross a source
            # line (let alone a paragraph boundary).
            if not between or not re.fullmatch(r"[ \t]+", between):
                break
            run.append(tokens[following])
            following += 1
        start, end = run[0].start(), run[-1].end()
        phrase = text[start:end]
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        if line_end < 0:
            line_end = len(text)
        runs.append({
            "phrase": phrase,
            "key": _key(phrase),
            "words": len(run),
            "sentence_start": _sentence_start(masked, start),
            "start": _utf16(text[:start]),
            "end": _utf16(text[:end]),
            "line": text.count("\n", 0, start) + 1,
            "context": text[line_start:line_end].strip(),
        })
        index = following
    return runs


def names_without_entries(vault_index) -> list[dict]:
    """Return stable, JSON-ready missing-name occurrences.

    Multiword proper-case phrases are retained on one occurrence. A single
    word must occur at least twice and at least once away from sentence start.
    """
    vault_index.ensure_ready()
    known = set(vault_index.titles) | set(vault_index.aliases)
    gathered = []
    counts = Counter()
    non_initial = set()
    for path in sorted(vault_index.entries):
        if (path in _ROOT_REFERENCE_NOTES or path.startswith("Ideas/") or
                path == "Templates" or path.startswith("Templates/")):
            continue
        for occurrence in _occurrences(vault_index.entries[path].raw):
            if occurrence["key"] in known:
                continue
            first = next(WORD_RE.finditer(occurrence["phrase"]), None)
            if (occurrence["words"] > 1 and first is not None and
                    _key(first.group()) in _CONNECTOR_PREFIX):
                continue
            gathered.append((path, occurrence))
            counts[occurrence["key"]] += 1
            if not occurrence["sentence_start"]:
                non_initial.add(occurrence["key"])

    occurrences = []
    for path, occurrence in gathered:
        if occurrence["words"] == 1 and (
                occurrence["key"] in _COMMON_SINGLE or
                counts[occurrence["key"]] < 2 or occurrence["key"] not in non_initial):
            continue
        occurrences.append({
            "path": path,
            "phrase": occurrence["phrase"],
            "context": occurrence["context"],
            "line": occurrence["line"],
            "start": occurrence["start"],
            "end": occurrence["end"],
        })
    occurrences.sort(key=lambda row: (_key(row["phrase"]), row["path"], row["start"]))
    grouped: dict[str, list[dict]] = {}
    for occurrence in occurrences:
        grouped.setdefault(_key(occurrence["phrase"]), []).append(occurrence)
    rows = []
    for phrase_key in sorted(grouped):
        phrase_rows = grouped[phrase_key]
        row = dict(phrase_rows[0])
        row["count"] = len(phrase_rows)
        row["sources"] = sorted({item["path"] for item in phrase_rows})
        rows.append(row)
    return rows


find_names = names_without_entries
