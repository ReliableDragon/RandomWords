"""Lossless parsing and safe rendering for the worldbuilding note subset.

Parsing is deliberately a view over the original text: callers edit ``raw``
and pass the complete updated text back through :func:`parse`.
"""
from __future__ import annotations

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


_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_ASIDE = re.compile(r"\$\{([^}]*)\}")
_TAG = re.compile(r"(?<![\w])#([\w-]+)", re.UNICODE)
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def _span(text: str, start: int, end: int) -> Span:
    return Span(len(text[:start].encode("utf-16-le")) // 2,
                len(text[:end].encode("utf-16-le")) // 2)


def _split_values(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    # The supported YAML subset uses simple scalars, optionally quoted.
    return [v.strip().strip("\"'") for v in value.split(",") if v.strip()]


def _header_link(raw: str, text: str, start: int, end: int) -> Link:
    inner = raw[2:-2]
    target, sep, display = inner.partition("|")
    target = target.strip()
    target, hashmark, heading = target.partition("#")
    return Link(target.strip(), display.strip() if sep else None,
                heading.strip() if hashmark else None, _span(text, start, end))


def _header_items(value: str, text: str = "", offset: int = 0) -> list[Link]:
    matches = list(_WIKILINK.finditer(value))
    if matches:
        return [Link(m.group(1).split("|", 1)[0].split("#", 1)[0].strip(),
                     (m.group(1).split("|", 1)[1].strip() if "|" in m.group(1) else None),
                     None, _span(text, offset + m.start(), offset + m.end())) for m in matches]
    return [Link(v.strip(), None, None, _span(text, offset, offset + len(value))) for v in _split_values(value)]


def parse(text: str, path: str, revision: str = "") -> Entry:
    """Parse supported metadata and inline references while retaining source."""
    path = path.replace("\\", "/")
    parts = path.split("/")
    title = parts[-1][:-3] if parts[-1].lower().endswith(".md") else parts[-1]
    kind, folder = (parts[0] if len(parts) > 1 else "", "/".join(parts[:-1]))
    entry = Entry(path, title, kind, folder, text, revision=revision)
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
                            value, text, offsets[row_index] + row.find(value))
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
            entry.from_targets.extend(_header_items(value, text, offsets[i] + line.find(value)))
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
        link = _header_link(match.group(), text, match.start(), match.end())
        entry.links.append(link)
    for match in _ASIDE.finditer(text):
        entry.notes.append(match.group(1))
    for match in _TAG.finditer(text[body_start:]):
        tag = match.group(1)
        if tag not in entry.tags: entry.tags.append(tag)
    cleaned = entry.body
    # Metadata-like directives, code fences and Base blocks are not prose.
    cleaned = re.sub(r"(?ms)^```(?:base)?\s*.*?^```\s*$", " ", cleaned)
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


def _inline(text: str, index=None) -> str:
    # Protect recognized constructs before escaping all remaining raw HTML.
    tokens = []
    def hold(value):
        tokens.append(value)
        return f"\x00{len(tokens)-1}\x00"
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
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", md_link, text)
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
    for i, value in enumerate(tokens): escaped = escaped.replace(f"\x00{i}\x00", value)
    return escaped


def render(entry: Entry, resolve_link=None, base_entries=None, base_resolve=None) -> str:
    """Render the supported vault subset to safe HTML."""
    lines = entry.body.splitlines()
    out, paragraph, list_open, quote_open = [], [], False, False
    in_fence = False
    fence_size = 3
    fence_language = ""
    fence_lines = []
    def flush():
        if paragraph:
            out.append("<p>" + "<br>\n".join(_inline(x, resolve_link) for x in paragraph) + "</p>")
            paragraph.clear()
    for line in lines:
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
            if list_open: out.append("</ul>"); list_open = False
            if quote_open: out.append("</blockquote>"); quote_open = False
            in_fence = True
            fence_size = len(opening.group(1))
            fence_language = opening.group(2).lower()
            fence_lines = [line]
            continue
        if not line.strip():
            flush()
            if list_open: out.append("</ul>"); list_open = False
            if quote_open: out.append("</blockquote>"); quote_open = False
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", line)
        if hm:
            flush()
            if list_open: out.append("</ul>"); list_open = False
            level = len(hm.group(1)); out.append(f"<h{level}>{_inline(hm.group(2), resolve_link)}</h{level}>")
            continue
        bm = re.match(r"^(\t*| *)(?:[-*+]\s+)(.*)$", line)
        if bm:
            flush()
            if quote_open: out.append("</blockquote>"); quote_open = False
            if not list_open: out.append("<ul>"); list_open = True
            depth = len(bm.group(1).expandtabs(4)) // 4
            out.append("<li" + (f' style="margin-left:{depth * 1.5}em"' if depth else "") + ">" + _inline(bm.group(2), resolve_link) + "</li>")
            continue
        if list_open: out.append("</ul>"); list_open = False
        qm = re.match(r"^>\s?(.*)$", line)
        if qm:
            flush()
            if not quote_open: out.append("<blockquote>"); quote_open = True
            out.append("<p>" + _inline(qm.group(1), resolve_link) + "</p>")
            continue
        if quote_open: out.append("</blockquote>"); quote_open = False
        if line.startswith("    ") or line.startswith("\t"):
            flush(); out.append("<pre><code>" + escape(line.lstrip(" \t")) + "</code></pre>")
        else:
            paragraph.append(line)
    flush()
    if in_fence:
        out.append("<pre><code>" + escape("\n".join(fence_lines)) + "</code></pre>")
    if list_open: out.append("</ul>")
    if quote_open: out.append("</blockquote>")
    return "\n".join(out)
