"""Lossless parsing and safe rendering for the worldbuilding note subset.

Parsing is deliberately a view over the original text: callers edit ``raw``
and pass the complete updated text back through :func:`parse`.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from html import escape
import re
from urllib.parse import quote, urlsplit


@dataclass(frozen=True)
class Span:
    start: int
    end: int


@dataclass(frozen=True)
class Link:
    target: str
    display: str | None = None
    heading: str | None = None
    span: Span | None = None
    resolved_path: str | None = None
    status: str = "unresolved"


@dataclass
class Entry:
    path: str
    title: str
    kind: str
    folder: str
    raw: str
    from_targets: list[Link] = field(default_factory=list)
    origin: list[str] = field(default_factory=list)
    glosses: dict[str, str] = field(default_factory=dict)
    themes: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    body: str = ""
    words: int = 0
    stub: bool = True
    frontmatter_supported: bool = True
    revision: str = ""


class _Scanned:
    """A regular expression whose matches are located by a linear scanner.

    ``re`` retries a failed search from every later position, so a pattern
    such as ``\\[\\[[^\\]]+\\]\\]`` is quadratic on a line of unclosed ``[[``.
    ``spans`` finds the same leftmost, non-overlapping matches in one pass;
    the pattern is then matched only within each span, to provide groups.
    """

    def __init__(self, pattern: str, spans):
        self.pattern = re.compile(pattern)
        self._spans = spans

    def finditer(self, text: str):
        for start, end in self._spans(text):
            yield self.pattern.fullmatch(text, start, end)

    def sub(self, repl, text: str) -> str:
        pieces, cursor = [], 0
        for match in self.finditer(text):
            pieces.append(text[cursor:match.start()])
            pieces.append(repl(match))
            cursor = match.end()
        pieces.append(text[cursor:])
        return "".join(pieces)


def _delimited(opener: str, stop: str, closer: str, minimum: int):
    """Spans of ``opener``, at least ``minimum`` characters other than
    ``stop``, then ``closer`` (which begins with ``stop``).

    Every opener before the next ``stop`` shares that ``stop``, so when one
    fails they all do and the scan resumes after it.
    """
    def spans(text: str):
        position = 0
        while True:
            start = text.find(opener, position)
            if start < 0:
                return
            inner = start + len(opener)
            end = text.find(stop, inner)
            if end < 0:
                return
            if end - inner >= minimum and text.startswith(closer, end):
                position = end + len(closer)
                yield start, position
            else:
                position = end + 1
    return spans


def _markdown_link_spans(text: str):
    """Spans of ``[label](url)``, as ``\\[([^\\]]+)\\]\\(([^)]+)\\)`` matches."""
    position, close = 0, -1
    while True:
        start = text.find("[", position)
        if start < 0:
            return
        bracket = text.find("]", start + 1)
        if bracket < 0:
            return
        position = bracket + 1
        if bracket > start + 1 and text.startswith("(", bracket + 1):
            # The first ")" after the "(" is reused until the scan passes it.
            if close < bracket + 2:
                close = text.find(")", bracket + 2)
                if close < 0:
                    return
            if close > bracket + 2:
                position = close + 1
                yield start, position


_WIKILINK = _Scanned(r"\[\[([^\]]+)\]\]", _delimited("[[", "]", "]]", 1))
_ASIDE = _Scanned(r"\$\{([^}]*)\}", _delimited("${", "}", "}", 0))
_MARKDOWN_LINK = _Scanned(r"\[([^\]]+)\]\(([^)]+)\)", _markdown_link_spans)
_WHITESPACE = re.compile(r"\s*")


def _fenced_block_spans(text: str):
    """Spans of ``(?ms)^```(?:base)?\\s*.*?^```\\s*$`` matches, linearly.

    A block runs from a line starting with three backticks to the next line
    that is three backticks and whitespace, plus any blank lines after it.
    Once a block has no closing line, no later one can have one either.
    """
    def fence_line(position):
        if position == 0 and text.startswith("```"):
            return 0
        found = text.find("\n```", max(position - 1, 0))
        return found + 1 if found >= 0 else -1
    start = fence_line(0)
    while start >= 0:
        close = fence_line(start + 3)
        while close >= 0:
            blank = _WHITESPACE.match(text, close + 3).end()
            if blank == len(text):
                end = blank
                break
            end = text.rfind("\n", close + 3, blank)
            if end >= 0:
                break
            close = fence_line(blank)
        if close < 0:
            return
        yield start, end
        start = fence_line(end)


def _without_fenced_blocks(text: str) -> str:
    """``re.sub(r"(?ms)^```(?:base)?\\s*.*?^```\\s*$", " ", text)``, linearly."""
    pieces, cursor = [], 0
    for start, end in _fenced_block_spans(text):
        pieces.append(text[cursor:start])
        pieces.append(" ")
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


_TAG = re.compile(r"(?<![\w])#([\w-]+)", re.UNICODE)
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


_ASTRAL = re.compile("[\U00010000-\U0010ffff]")


def _utf16_offsets(text: str):
    """Map offsets in ``text`` to UTF-16 (JavaScript) offsets.

    Each character outside the Basic Multilingual Plane is two UTF-16 code
    units, so an offset grows by the number of such characters before it.
    """
    astral = [match.start() for match in _ASTRAL.finditer(text)]
    return lambda offset: offset + bisect_left(astral, offset)


def _span(utf16, start: int, end: int) -> Span:
    return Span(utf16(start), utf16(end))


def _split_values(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    # The supported YAML subset uses simple scalars, optionally quoted.
    return [v.strip().strip("\"'") for v in value.split(",") if v.strip()]


def _header_link(raw: str, utf16, start: int, end: int) -> Link:
    inner = raw[2:-2]
    target, sep, display = inner.partition("|")
    target = target.strip()
    target, hashmark, heading = target.partition("#")
    return Link(target.strip(), display.strip() if sep else None,
                heading.strip() if hashmark else None, _span(utf16, start, end))


def _header_items(value: str, utf16, offset: int = 0) -> list[Link]:
    matches = list(_WIKILINK.finditer(value))
    if matches:
        return [Link(m.group(1).split("|", 1)[0].split("#", 1)[0].strip(),
                     (m.group(1).split("|", 1)[1].strip() if "|" in m.group(1) else None),
                     None, _span(utf16, offset + m.start(), offset + m.end())) for m in matches]
    return [Link(v.strip(), None, None, _span(utf16, offset, offset + len(value))) for v in _split_values(value)]


def parse(text: str, path: str, revision: str = "") -> Entry:
    """Parse supported metadata and inline references while retaining source."""
    path = path.replace("\\", "/")
    parts = path.split("/")
    title = parts[-1][:-3] if parts[-1].lower().endswith(".md") else parts[-1]
    kind, folder = (parts[0] if len(parts) > 1 else "", "/".join(parts[:-1]))
    entry = Entry(path, title, kind, folder, text, revision=revision)
    utf16 = _utf16_offsets(text)
    lines = text.splitlines(keepends=True)
    offsets = []
    n = 0
    for line in lines:
        offsets.append(n)
        n += len(line)
    body_start = 0
    fm_end = 0
    if lines and lines[0].lstrip("\ufeff").strip() == "---":
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is not None:
            fm_end = close + 1
            fm = [line.rstrip("\r\n") for line in lines[1:close]]
            key = None
            for row_index, row in enumerate(fm, start=1):
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", row)
                if m:
                    key, value = m.group(1).lower(), m.group(2)
                    if key == "aliases":
                        if value:
                            entry.aliases.extend(_split_values(value))
                        else:
                            entry.aliases = []
                    elif key == "from":
                        entry.from_targets = _header_items(
                            value, utf16, offsets[row_index] + row.find(value))
                    elif key in ("origin", "source"):
                        entry.origin, entry.glosses = _parse_origin(value)
                    elif key == "themes":
                        entry.themes = _split_values(value)
                    else:
                        key = None
                elif key == "aliases" and re.match(r"^\s+-\s*", row):
                    entry.aliases.extend(_split_values(re.sub(r"^\s+-\s*", "", row)))
                elif row.strip() and not row.lstrip().startswith("#"):
                    entry.frontmatter_supported = False
            body_start = offsets[fm_end] if fm_end < len(offsets) else len(text)
    # First-line headers are consecutive and remain in the raw source.
    i = fm_end
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        m = re.match(r"^(From|Origin|Source|Themes):\s*(.*)$", line, re.I)
        if not m:
            break
        key, value = m.group(1).lower(), m.group(2)
        if key == "from":
            entry.from_targets.extend(_header_items(value, utf16, offsets[i] + line.find(value)))
        elif key in ("origin", "source"):
            entry.origin, entry.glosses = _parse_origin(value)
        else:
            entry.themes = _split_values(value)
        i += 1
        body_start = offsets[i] if i < len(offsets) else len(text)
    entry.body = text[body_start:]
    masked = list(text)
    if body_start:
        for j in range(body_start):
            if masked[j] not in "\r\n": masked[j] = " "
    for match in _WIKILINK.finditer(text):
        link = _header_link(match.group(), utf16, match.start(), match.end())
        entry.links.append(link)
    for match in _ASIDE.finditer(text):
        entry.notes.append(match.group(1))
    for match in _TAG.finditer(text[body_start:]):
        tag = match.group(1)
        if tag not in entry.tags: entry.tags.append(tag)
    cleaned = entry.body
    # Metadata-like directives, code fences and Base blocks are not prose.
    cleaned = _without_fenced_blocks(cleaned)
    entry.words = len(_WORD.findall(cleaned))
    entry.stub = entry.words < 20
    return entry


def _parse_origin(value: str) -> tuple[list[str], dict[str, str]]:
    # Glosses are balanced so punctuation inside a definition (including
    # parenthetical editorial notes) cannot be mistaken for later seed words.
    values, glosses = [], {}
    pos = 0
    while pos < len(value):
        while pos < len(value) and (value[pos].isspace() or value[pos] == ","):
            pos += 1
        if pos >= len(value):
            break
        start = pos
        while pos < len(value) and not value[pos].isspace() and value[pos] != ",":
            pos += 1
        word = value[start:pos].strip()
        if not word:
            continue
        values.append(word)

        lookahead = pos
        while lookahead < len(value) and value[lookahead].isspace():
            lookahead += 1
        gloss = None
        if value.startswith(r"\[", lookahead):
            close = value.find(r"\]", lookahead + 2)
            if close >= 0:
                gloss = value[lookahead + 2:close]
                pos = close + 2
        elif lookahead < len(value) and value[lookahead] == "(":
            depth = 1
            cursor = lookahead + 1
            while cursor < len(value) and depth:
                if value[cursor] == "(":
                    depth += 1
                elif value[cursor] == ")":
                    depth -= 1
                cursor += 1
            if depth == 0:
                gloss = value[lookahead + 1:cursor - 1]
                pos = cursor
        if gloss is not None:
            glosses[word] = gloss.strip()
    return values, glosses


def _safe_external_url(url: str) -> bool:
    # Reject controls, whitespace and encoded/control obfuscation before parsing.
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in url) or any(ch.isspace() for ch in url):
        return False
    lowered = url.lower()
    if re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", lowered):
        return False
    scheme = urlsplit(url).scheme.lower()
    return scheme in {"http", "https", "mailto"}


def _target_href(target: str, index) -> str | None:
    # Internal target text is never used directly as an href. An index may map
    # canonical paths; unresolved links stay inert.
    if index is None:
        return None
    result = None
    if callable(index):
        result = index(target)
    elif hasattr(index, "resolve"):
        result = index.resolve(target)
    elif isinstance(index, dict):
        result = index.get(target)
    if isinstance(result, str): path = result
    elif isinstance(result, dict): path = result.get("path") or result.get("resolved_path")
    else: path = getattr(result, "path", None) or getattr(result, "resolved_path", None)
    return "/world/entry?path=" + quote(path, safe="/") if path else None


_PLACEHOLDER = re.compile(r"\x00(\d+)\x00")
_MAX_NESTING = 8
_BACKTICKS = re.compile(r"`+")
_EMBED = re.compile(r"!\[\[[^\]]{0,500}\]\]")
_IMAGE = re.compile(r"!\[[^\]]{0,500}\]\((?:[^()]|\([^()]*\)){0,1000}\)")
_TASK_BOX = re.compile(r"^\[[ xX]\](?=\s|$)\s?")
# No two whitespace runs are adjacent, so a long blank run cannot be split
# between them in quadratically many ways.
_TABLE_SEPARATOR = re.compile(r"^\s*(?:\|\s*)?:?-+:?\s*(?:\|\s*:?-+:?\s*)*(?:\|\s*)?$")


def _table_start(header: str, separator: str) -> bool:
    """A header row of two or more cells over a separator row containing ``|``.

    Without both, a line with a ``|`` above a ``---`` line is prose over a rule.
    """
    return ("|" in separator and bool(_TABLE_SEPARATOR.match(separator))
            and len(_table_cells(header)) >= 2 and len(_table_cells(separator)) >= 2)


def _table_cells(row: str) -> list[str]:
    """Cells of a pipe-separated row, ignoring the optional outer pipes."""
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return re.split(r"(?<!\\)\|", row) if row.strip() else []


_RULE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_BULLET = re.compile(r"^(\t*| *)(?:[-*+]\s+)(.*)$")
_NUMBERED = re.compile(r"^(\t*| *)(\d{1,9})[.)]\s+(.*)$")


def _code_spans(text: str, hold) -> str:
    """Replace backtick code spans with held ``<code>`` elements.

    A span opens at a run of backticks and closes at the next run of exactly
    the same length; an unmatched run stays literal. Linear in the number of
    runs, unlike a lazy regular expression.
    """
    runs = [(m.start(), m.end()) for m in _BACKTICKS.finditer(text)]
    if not runs:
        return text
    by_length: dict[int, list[int]] = {}
    for position, (start, end) in enumerate(runs):
        by_length.setdefault(end - start, []).append(position)
    pieces, cursor, position = [], 0, 0
    while position < len(runs):
        start, end = runs[position]
        candidates = by_length[end - start]
        later = bisect_right(candidates, position)
        if later >= len(candidates):
            position += 1
            continue
        close_start, close_end = runs[candidates[later]]
        pieces.append(text[cursor:start])
        pieces.append(hold("<code>" + escape(text[end:close_start]) + "</code>"))
        cursor = close_end
        position = candidates[later] + 1
    pieces.append(text[cursor:])
    return "".join(pieces)


def _note_skip(skipped, kind: str) -> None:
    if skipped is not None and kind not in skipped:
        skipped.append(kind)


def _unsupported(text: str, kind: str, skipped) -> str:
    """Escaped raw text for a construct the renderer does not draw."""
    _note_skip(skipped, kind)
    return f'<span class="world-unsupported" data-kind="{kind}">{escape(text)}</span>'


def _inline(text: str, index=None, skipped=None) -> str:
    # Protect recognized constructs before escaping all remaining raw HTML.
    tokens = []
    def hold(value):
        tokens.append(value)
        return f"\x00{len(tokens)-1}\x00"
    # The placeholder delimiter must not be forgeable from the note itself.
    text = text.replace("\x00", "")
    # Code spans first: nothing inside backticks is interpreted.
    text = _code_spans(text, hold)
    # Embeds and images are not drawn; their raw text stays visible and inert.
    text = _EMBED.sub(lambda m: hold(_unsupported(m.group(0), "embed", skipped)), text)
    text = _IMAGE.sub(lambda m: hold(_unsupported(m.group(0), "image", skipped)), text)
    def wiki(m):
        inner = m.group(1)
        target, _, label = inner.partition("|")
        target, hashmark, heading = target.partition("#")
        label = label.strip() if label else target.rsplit("/", 1)[-1]
        href = _target_href(target.strip(), index)
        if href and heading: href += "#" + quote(heading.strip(), safe="-")
        rendered = f'<a href="{escape(href, quote=True)}">{escape(label)}</a>' if href else escape(m.group(0))
        return hold(rendered)
    text = _WIKILINK.sub(wiki, text)
    text = _ASIDE.sub(lambda m: hold('<aside class="entry-note">' + escape(m.group(1)) + '</aside>'), text)
    # Markdown/bare links are accepted only after independent URL validation.
    def md_link(m):
        label, url = m.group(1), m.group(2)
        if _safe_external_url(url):
            return hold(f'<a href="{escape(url, quote=True)}" rel="noopener noreferrer">{escape(label)}</a>')
        return hold(escape(m.group(0)))
    text = _MARKDOWN_LINK.sub(md_link, text)
    def bare(m):
        url = m.group(0)
        if _safe_external_url(url):
            return hold(f'<a href="{escape(url, quote=True)}" rel="noopener noreferrer">{escape(url)}</a>')
        return hold(escape(url))
    text = re.sub(r'(?<![\w"\'=])(?:https?://|mailto:)[^\s<>]+', bare, text, flags=re.I)
    escaped = escape(text, quote=False)
    # Inline emphasis, with delimiters applied to already escaped text.
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"~~(.+?)~~", r"<del>\1</del>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    # A held token may itself contain placeholders (a code span inside a link
    # label), always for earlier tokens, so a few passes settle it. The bound
    # keeps the cost linear in the text however the tokens nest.
    def substitute(m):
        return tokens[int(m.group(1))] if int(m.group(1)) < len(tokens) else m.group(0)
    for _ in range(_MAX_NESTING):
        replaced = _PLACEHOLDER.sub(substitute, escaped)
        if replaced == escaped:
            break
        escaped = replaced
    return escaped


def _item(text: str, index, skipped) -> str:
    """List item content; a task-list checkbox is kept as visible raw text."""
    box = _TASK_BOX.match(text)
    if box:
        return (_unsupported(box.group(0).rstrip(), "task", skipped) + " " +
                _inline(text[box.end():], index, skipped))
    return _inline(text, index, skipped)


def render(entry: Entry, resolve_link=None, base_entries=None, base_resolve=None,
           skipped=None) -> str:
    """Render the supported vault subset to safe HTML.

    Constructs that are recognised but not drawn (tables, images, embeds and
    task-list checkboxes) keep their escaped raw text inside a
    ``world-unsupported`` element. When ``skipped`` is a list, the kinds
    found are appended to it once each, in order of first appearance.
    """
    lines = entry.body.splitlines()
    out, paragraph, quote_open = [], [], False
    list_kind = None  # "ul", "ol" or None
    in_fence = False
    fence_size = 3
    fence_language = ""
    fence_lines = []
    def inline(value):
        return _inline(value, resolve_link, skipped)
    def flush():
        if paragraph:
            out.append("<p>" + "<br>\n".join(inline(x) for x in paragraph) + "</p>")
            paragraph.clear()
    def close_list():
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None
    def close_quote():
        nonlocal quote_open
        if quote_open:
            out.append("</blockquote>")
            quote_open = False
    def list_item(kind, indent, content, start=None):
        nonlocal list_kind
        if list_kind != kind:
            close_list()
            out.append(f'<ol start="{start}">' if kind == "ol" and start not in (None, 1)
                       else f"<{kind}>")
            list_kind = kind
        depth = len(indent.expandtabs(4)) // 4
        out.append("<li" + (f' style="margin-left:{depth * 1.5}em"' if depth else "") + ">"
                   + _item(content, resolve_link, skipped) + "</li>")
    position = 0
    while position < len(lines):
        line = lines[position]
        position += 1
        if in_fence:
            close = re.match(r"^\s*(`{3,})\s*$", line)
            if close and len(close.group(1)) >= fence_size:
                fence_lines.append(line)
                if fence_language == "base" and base_entries is not None:
                    from base_filters import evaluate
                    result = evaluate("\n".join(fence_lines[1:-1]), entry, base_entries, base_resolve)
                    if result.supported:
                        cards = []
                        for path in result.paths:
                            label = path.rsplit("/", 1)[-1]
                            if label.lower().endswith(".md"):
                                label = label[:-3]
                            href = "/world/entry?path=" + quote(path, safe="/")
                            cards.append(f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>')
                        out.append('<div class="base-results"><ul>' + "".join(cards) + '</ul></div>')
                    else:
                        out.append('<div class="base-diagnostic">' + escape(result.diagnostic or "Unsupported Base filter") + '</div>')
                        out.append("<pre><code>" + escape("\n".join(fence_lines)) + "</code></pre>")
                else:
                    out.append("<pre><code>" + escape("\n".join(fence_lines)) + "</code></pre>")
                fence_lines = []
                in_fence = False
                fence_language = ""
            else:
                fence_lines.append(line)
            continue
        opening = re.match(r"^\s*(`{3,})([A-Za-z0-9_-]*)\s*$", line)
        if opening:
            flush()
            close_list()
            close_quote()
            in_fence = True
            fence_size = len(opening.group(1))
            fence_language = opening.group(2).lower()
            fence_lines = [line]
            continue
        if not line.strip():
            flush()
            close_list()
            close_quote()
            continue
        if ("|" in line and position < len(lines)
                and _table_start(line, lines[position])):
            flush()
            close_list()
            close_quote()
            rows = [line, lines[position]]
            position += 1
            while position < len(lines) and lines[position].strip() and "|" in lines[position]:
                rows.append(lines[position])
                position += 1
            _note_skip(skipped, "table")
            out.append('<div class="world-unsupported" data-kind="table">'
                       + "<br>\n".join(escape(row) for row in rows) + "</div>")
            continue
        if _RULE.match(line):
            flush()
            close_list()
            close_quote()
            out.append("<hr>")
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", line)
        if hm:
            flush()
            close_list()
            level = len(hm.group(1)); out.append(f"<h{level}>{inline(hm.group(2))}</h{level}>")
            continue
        bm = _BULLET.match(line)
        if bm:
            flush()
            close_quote()
            list_item("ul", bm.group(1), bm.group(2))
            continue
        nm = _NUMBERED.match(line)
        if nm:
            flush()
            close_quote()
            list_item("ol", nm.group(1), nm.group(3), int(nm.group(2)))
            continue
        close_list()
        qm = re.match(r"^>\s?(.*)$", line)
        if qm:
            flush()
            if not quote_open: out.append("<blockquote>"); quote_open = True
            out.append("<p>" + inline(qm.group(1)) + "</p>")
            continue
        close_quote()
        if line.startswith("    ") or line.startswith("\t"):
            flush(); out.append("<pre><code>" + escape(line.lstrip(" \t")) + "</code></pre>")
        else:
            paragraph.append(line)
    flush()
    if in_fence:
        out.append("<pre><code>" + escape("\n".join(fence_lines)) + "</code></pre>")
    close_list()
    close_quote()
    return "\n".join(out)
