"""Pure reports for the deliberately small story-note convention."""
from __future__ import annotations

from html import escape
import os
import re
from urllib.parse import quote, unquote

from entry import _WIKILINK, render


_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def story_folders(folders, vault=None):
    """Canonicalize configured folders without guessing at vault paths."""
    result = []
    for folder in folders or ():
        if not isinstance(folder, str):
            continue
        value = folder.replace("\\", "/")
        if (not value or value.startswith("/") or any(part in ("", ".", "..") or part.startswith(".")
                                                        for part in value.split("/"))):
            raise ValueError("Story folders must be canonical vault-relative directories.")
        if vault is not None:
            full = vault.resolve(value)
            if not os.path.isdir(full) or vault.relative(full) != value:
                raise ValueError("Story folders must be existing canonical vault directories.")
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
    result, current, quote_mark = [], [], None
    for char in value + ",":
        if char in "\"'":
            if quote_mark is None:
                quote_mark = char
            elif quote_mark == char:
                quote_mark = None
            current.append(char)
        elif char == "," and quote_mark is None:
            item = "".join(current).strip().strip("\"'")
            if item:
                result.append(item)
            current = []
        else:
            current.append(char)
    return result


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
        result["diagnostics"].append("Story `when` is missing; this scene sorts last.")
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
            if current not in ("when", "where", "who", "aliases"):
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
        if list_item and current in ("where", "who", "aliases") and current in values:
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
            resolution = index.resolve(target, source)
            candidates = list(getattr(resolution, "candidates", ()))
            if getattr(resolution, "status", None) == "ambiguous":
                rows.append({"target": target, "candidates": candidates,
                             "diagnostic": "Ambiguous metadata reference."})
            else:
                rows.append({"target": target, "diagnostic": "Unresolved metadata reference."})
    return rows


def _body_mentions(index, entry, body):
    """Find resolved prose mentions, keeping metadata out of the scan."""
    found, diagnostics = {}, []
    plain_body = _WIKILINK.sub(lambda match: " " * len(match.group()), body)
    names = {name for candidate in index.entries.values()
             for name in [candidate.title, *candidate.aliases] if name}
    for name in sorted(names, key=lambda item: (item.casefold(), item)):
        resolution = index.resolve(name, entry.path)
        path = getattr(resolution, "path", None)
        status = getattr(resolution, "status", None)
        positions = [match.start() for match in re.finditer(
            r"(?<!\w)" + re.escape(name) + r"(?!\w)", plain_body, re.I)]
        if positions and not path:
            if status == "ambiguous":
                diagnostics.append(f"Ambiguous prose reference: {name}.")
            continue
        if path and path != entry.path and positions:
            candidate = index.entries[path]
            found[path] = {"path": path, "title": candidate.title,
                           "first": min(positions), "later": sorted(set(positions))[1:]}
        # Wikilinks require resolution because titles may collide.
        for match in _WIKILINK.finditer(body):
            target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
            resolved = _resolved(index, target, entry.path)
            if resolved and resolved != entry.path:
                candidate = index.entries[resolved]
                row = found.setdefault(resolved, {"path": resolved, "title": candidate.title,
                                                  "first": match.start(), "later": []})
                if match.start() < row["first"]:
                    row["later"].append(row["first"])
                    row["first"] = match.start()
                elif match.start() != row["first"]:
                    row["later"].append(match.start())
    for row in found.values():
        row["later"] = sorted(set(row["later"]))
    return list(sorted(found.values(), key=lambda row: (row["first"], row["path"]))), diagnostics


def report(index, folders):
    scenes = []
    for path in _scene_paths(index.entries, folders):
        entry = index.entries[path]
        meta = parse_scene(entry.raw)
        where, who = _references(index, path, meta["where"]), _references(index, path, meta["who"])
        reference_diagnostics = [f"{row['diagnostic']} {row['target']}"
                                 for row in [*where, *who] if "diagnostic" in row]
        scene = {"path": path, "title": entry.title, "when": meta["when"],
                 "diagnostics": [*meta["diagnostics"], *reference_diagnostics],
                 "where": where, "who": who}
        appearances, mention_diagnostics = _body_mentions(index, entry, meta["body"])
        scene["appearances"] = appearances
        scene["diagnostics"] = [*scene["diagnostics"], *mention_diagnostics]
        scenes.append(scene)
    scenes.sort(key=lambda row: (row["when"] is None, row["when"] if row["when"] is not None else 0,
                                 row["path"]))
    aggregate = {}
    for scene in scenes:
        for appearance in scene["appearances"]:
            row = aggregate.setdefault(appearance["path"], {"path": appearance["path"],
                                      "title": appearance["title"], "first_scene": scene["path"],
                                      "later_scenes": []})
            if row["first_scene"] != scene["path"] and scene["path"] not in row["later_scenes"]:
                row["later_scenes"].append(scene["path"])
    return {"folders": list(story_folders(folders)), "scenes": scenes,
            "appearances": list(aggregate.values()),
            "diagnostics": [{"path": scene["path"], "message": message}
                            for scene in scenes for message in scene["diagnostics"]]}


def quotes(index, by=None):
    if by and (by not in index.entries or not by.startswith("People/")):
        raise ValueError("Quotation speaker must be a canonical People note path.")
    rows = []
    for path, entry in sorted(index.entries.items()):
        lines = entry.body.splitlines()
        for start, line in enumerate(lines):
            if not line.startswith(">") or (start and lines[start - 1].startswith(">")):
                continue
            end, quote_lines = start, []
            while end < len(lines) and lines[end].startswith(">"):
                quote_lines.append(lines[end][1:].lstrip())
                end += 1
            if end >= len(lines):
                continue
            match = re.fullmatch(r"-\s*\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]\s*", lines[end])
            if not match:
                continue
            speaker = _resolved(index, match.group(1).strip(), path)
            if not speaker or (by and speaker != by):
                continue
            rows.append({"path": path, "title": entry.title, "text": "\n".join(quote_lines).strip(),
                         "speaker": {"path": speaker, "title": index.entries[speaker].title}})
    return {"by": by, "quotes": rows}


def _anchor(path):
    return "entry-" + quote(path, safe="")


def _render_export_entry(index, entry, anchors):
    html = render(entry, lambda target: index.resolve(target, entry.path),
                  base_entries=list(index.entries.values()),
                  base_resolve=lambda target, source: index.resolve(target, source))
    def local(match):
        path = unquote(match.group(1))
        return f'href="#{anchors[path]}"' if path in anchors else match.group(0)
    return re.sub(r'href="/world/entry\?path=([^"#]+)"', local, html)


def export(index, folders, path=None):
    configured = story_folders(folders)
    if path in (None, "", "story"):
        story_data = report(index, configured)
        selected = [row["path"] for row in story_data["scenes"]]
    else:
        story_data = None
        prefix = path.rstrip("/") + "/"
        selected = sorted(item for item in index.entries if item.startswith(prefix))
        if not selected:
            raise ValueError("Export path must name a vault folder or `story`.")
    glossary, seen = [], set()
    def add(item):
        if item and item not in seen:
            seen.add(item)
            glossary.append(item)
    if story_data is not None:
        for scene in story_data["scenes"]:
            for reference in [*scene["where"], *scene["who"]]:
                add(reference.get("path"))
            for appearance in scene["appearances"]:
                add(appearance["path"])
    else:
        for item in selected:
            entry = index.entries[item]
            meta = parse_scene(entry.raw)
            for target in [*meta["where"], *meta["who"]]:
                add(_resolved(index, target, item))
            for appearance in _body_mentions(index, entry, meta["body"])[0]:
                add(appearance["path"])
    if path not in (None, "", "story"):
        glossary.sort(key=lambda item: (index.entries[item].title.casefold(), item))
    title = "Story" if path in (None, "", "story") else path
    anchors = {item: _anchor(item) for item in selected}
    anchors.update({item: "glossary-" + quote(item, safe="") for item in glossary if item not in anchors})
    parts = ["<!doctype html><html><head><meta charset=\"utf-8\"><title>" + escape(title) +
             "</title><style>:root{color:#201f1c;background:#f7f4ec;font:18px Georgia,serif}"
             "body{max-width:48rem;margin:3rem auto;padding:0 1rem;line-height:1.55}"
             "h1,h2{font-family:system-ui,sans-serif}article,section{margin:2rem 0}"
             "a{color:#285f4d}</style></head><body><main><h1>" + escape(title) + "</h1>"]
    for item in selected:
        entry = index.entries[item]
        parts.append(f'<article id="{_anchor(item)}"><h2>{escape(entry.title)}</h2>' +
                     _render_export_entry(index, entry, anchors) + "</article>")
    parts.append("<section><h2>Glossary</h2><ul>")
    for item in glossary:
        target = anchors[item]
        if item in selected:
            parts.append(f'<li><a href="#{target}">{escape(index.entries[item].title)}</a></li>')
        else:
            parts.append(f'<li id="{target}"><strong>{escape(index.entries[item].title)}</strong>' +
                         _render_export_entry(index, index.entries[item], anchors) + "</li>")
    parts.append("</ul></section></main></body></html>")
    return {"path": path or "story", "html": "".join(parts), "entries": selected,
            "glossary": [{"path": item, "title": index.entries[item].title} for item in glossary]}
