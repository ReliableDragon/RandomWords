"""Pure reports for the deliberately small story-note convention."""
from __future__ import annotations

from html import escape
import re
from urllib.parse import quote

from entry import _WIKILINK, render


_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def story_folders(folders):
    """Canonicalize configured folders without guessing at vault paths."""
    result = []
    for folder in folders or ():
        if not isinstance(folder, str):
            continue
        value = folder.replace("\\", "/").strip(" /")
        if value and value not in result:
            result.append(value)
    return tuple(result)


def _values(value):
    value = value.strip()
    if ((value.startswith('"') and value.endswith('"')) or
            (value.startswith("'") and value.endswith("'"))):
        value = value[1:-1].strip()
    if value.startswith("[[") and value.endswith("]]" ):
        return [value]
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if not value:
        return []
    return [part.strip().strip("\"'") for part in value.split(",") if part.strip()]


def _links(values):
    result = []
    for value in values:
        match = re.fullmatch(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]", value.strip())
        if match:
            result.append(match.group(1).strip())
        else:
            result.append(value.strip())
    return result


def parse_scene(raw):
    """Return raw-preserving scene metadata and diagnostics for supported YAML."""
    result = {"when": None, "where": [], "who": [], "body": raw,
              "diagnostics": [], "frontmatter": False}
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return result
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        result["diagnostics"].append("Unclosed story frontmatter.")
        return result
    result["frontmatter"] = True
    result["body"] = "".join(lines[close + 1:])
    rows = [(line.rstrip("\r\n"), i + 2) for i, line in enumerate(lines[1:close])]
    values, supported = {}, True
    current = None
    for row, line_number in rows:
        match = _KEY.match(row)
        if match:
            current, value = match.group(1).lower(), match.group(2)
            if current not in ("when", "where", "who"):
                supported = False
                continue
            if value.lstrip().startswith(("{", "&", "*", "|", ">")):
                supported = False
                continue
            if value:
                values[current] = _values(value)
            else:
                values[current] = []
            continue
        list_item = re.match(r"^\s+-\s+(.+)$", row)
        if list_item and current in ("where", "who") and current in values:
            values[current].extend(_values(list_item.group(1)))
            continue
        if row.strip() and not row.lstrip().startswith("#"):
            supported = False
    if not supported:
        result["diagnostics"].append("Unsupported story frontmatter; metadata was not interpreted.")
        return result
    if any(not re.fullmatch(r"\[\[[^\]]+\]\]", value.strip())
           for key in ("where", "who") for value in values.get(key, [])):
        result["diagnostics"].append("Unsupported story frontmatter; metadata was not interpreted.")
        return result
    when = values.get("when", [])
    if len(when) == 1 and re.fullmatch(r"[+-]?\d+", when[0]):
        result["when"] = int(when[0])
    elif "when" in values:
        result["diagnostics"].append("Story `when` must be an integer; this scene sorts last.")
    else:
        result["diagnostics"].append("Story `when` is missing; this scene sorts last.")
    result["where"] = _links(values.get("where", []))
    result["who"] = _links(values.get("who", []))
    return result


def _scene_paths(entries, folders):
    prefixes = tuple(folder + "/" for folder in story_folders(folders))
    return [path for path in entries if path.startswith(prefixes)]


def _resolved(index, target, source):
    result = index.resolve(target, source)
    return getattr(result, "path", None)


def _references(index, source, targets):
    rows = []
    for target in targets:
        path = _resolved(index, target, source)
        if path:
            entry = index.entries[path]
            rows.append({"path": path, "title": entry.title})
        else:
            rows.append({"target": target, "diagnostic": "Unresolved metadata reference."})
    return rows


def _body_mentions(index, entry, body):
    """Find resolved prose mentions, keeping metadata out of the scan."""
    found = {}
    plain_body = _WIKILINK.sub(lambda match: " " * len(match.group()), body)
    for path, candidate in index.entries.items():
        if path == entry.path:
            continue
        names = [candidate.title, *candidate.aliases]
        positions = []
        for name in names:
            if name:
                positions.extend(match.start() for match in re.finditer(
                    r"(?<!\w)" + re.escape(name) + r"(?!\w)", plain_body, re.I))
        # Wikilinks require resolution because titles may collide.
        for match in _WIKILINK.finditer(body):
            target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
            if _resolved(index, target, entry.path) == path:
                positions.append(match.start())
        if positions:
            found[path] = {"path": path, "title": candidate.title,
                           "first": min(positions), "later": sorted(set(positions))[1:]}
    return list(sorted(found.values(), key=lambda row: (row["first"], row["path"])))


def report(index, folders):
    scenes = []
    for path in _scene_paths(index.entries, folders):
        entry = index.entries[path]
        meta = parse_scene(entry.raw)
        scene = {"path": path, "title": entry.title, "when": meta["when"],
                 "diagnostics": meta["diagnostics"],
                 "where": _references(index, path, meta["where"]),
                 "who": _references(index, path, meta["who"]),
                 "appearances": _body_mentions(index, entry, meta["body"])}
        scenes.append(scene)
    scenes.sort(key=lambda row: (row["when"] is None, row["when"] if row["when"] is not None else 0,
                                 row["path"]))
    return {"folders": list(story_folders(folders)), "scenes": scenes,
            "diagnostics": [{"path": scene["path"], "message": message}
                            for scene in scenes for message in scene["diagnostics"]]}


_QUOTE = re.compile(r"(?ms)(?:^|\n)>?\s*(.+?)\s*\n\s*-\s*\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def quotes(index, by=None):
    if by and by not in index.entries:
        raise ValueError("Quotation speaker must be a canonical vault path.")
    rows = []
    for path, entry in sorted(index.entries.items()):
        for match in _QUOTE.finditer(entry.body):
            speaker = _resolved(index, match.group(2).strip(), path)
            if not speaker or (by and speaker != by):
                continue
            rows.append({"path": path, "title": entry.title, "text": match.group(1).strip(),
                         "speaker": {"path": speaker, "title": index.entries[speaker].title}})
    return {"by": by, "quotes": rows}


def _anchor(path):
    return "entry-" + quote(path, safe="")


def _render_export_entry(index, entry):
    html = render(entry, lambda target: index.resolve(target, entry.path),
                  base_entries=list(index.entries.values()),
                  base_resolve=lambda target, source: index.resolve(target, source))
    def local(match):
        path = match.group(1)
        return f'href="#{_anchor(path)}"' if path in index.entries else match.group(0)
    return re.sub(r'href="/world/entry\?path=([^"#]+)"', local, html)


def export(index, folders, path=None):
    configured = story_folders(folders)
    if path in (None, "", "story"):
        selected = [row["path"] for row in report(index, configured)["scenes"]]
    else:
        prefix = path.rstrip("/") + "/"
        selected = sorted(item for item in index.entries if item.startswith(prefix))
        if not selected:
            raise ValueError("Export path must name a vault folder or `story`.")
    glossary = []
    seen = set()
    for item in selected:
        entry = index.entries[item]
        for match in _WIKILINK.finditer(entry.body):
            target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
            resolved = _resolved(index, target, item)
            if resolved and resolved not in seen:
                seen.add(resolved)
                glossary.append(resolved)
    if path not in (None, "", "story"):
        glossary.sort(key=lambda item: (index.entries[item].title.casefold(), item))
    title = "Story" if path in (None, "", "story") else path
    parts = ["<!doctype html><html><head><meta charset=\"utf-8\"><title>" + escape(title) +
             "</title></head><body><main><h1>" + escape(title) + "</h1>"]
    for item in selected:
        entry = index.entries[item]
        parts.append(f'<article id="{_anchor(item)}"><h2>{escape(entry.title)}</h2>' +
                     _render_export_entry(index, entry) + "</article>")
    parts.append("<section><h2>Glossary</h2><ul>")
    for item in glossary:
        parts.append(f'<li id="{_anchor(item)}"><a href="#{_anchor(item)}">{escape(index.entries[item].title)}</a></li>')
    parts.append("</ul></section></main></body></html>")
    return {"path": path or "story", "html": "".join(parts), "entries": selected,
            "glossary": [{"path": item, "title": index.entries[item].title} for item in glossary]}
