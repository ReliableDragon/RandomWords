"""HTTP routes for the optional worldbuilding vault."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import os
import json
import re
import hashlib

from entry import parse, render
from vault import (DestinationConflict, FolderConflict, InvalidPath, RevisionConflict,
                   UnreadableSource)
from web_routes import Response


MAX_TEXT = 1_000_000
MAX_RESULTS = 100


def _fail(status, message, data=None):
    payload = {"ok": False, "message": message}
    if data is not None:
        payload["data"] = data
    return Response(status, payload)


def _ok(message, data):
    return Response(200, {"ok": True, "message": message, "data": data})


def _entry_dict(entry):
    result = asdict(entry) if is_dataclass(entry) else dict(entry)
    return result


def _index_entries(index):
    if index is None:
        return []
    for name in ("entries", "by_path", "notes"):
        value = getattr(index, name, None)
        if isinstance(value, dict):
            return list(value.values())
        if isinstance(value, (list, tuple)):
            return list(value)
    return []


def _entry_at(index, path):
    if index is None:
        return None
    for name in ("entries", "by_path", "notes"):
        value = getattr(index, name, None)
        if isinstance(value, dict) and path in value:
            return value[path]
    for method in ("get_entry", "entry", "get"):
        fn = getattr(index, method, None)
        if callable(fn):
            try:
                found = fn(path)
                if found is not None:
                    return found
            except (KeyError, TypeError, ValueError):
                pass
    return None


def _resolve(req, target, source_path=None):
    result = _resolution(req, target, source_path)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("path") or result.get("resolved_path")
    return (getattr(result, "path", None) or getattr(result, "resolved_path", None)) if result is not None else None


def _resolution(req, target, source_path=None):
    index = req.world_index
    if index is None:
        return None
    fn = getattr(index, "resolve_link", None) or getattr(index, "resolve", None)
    if callable(fn):
        try:
            try:
                return fn(target, source_path=source_path)
            except TypeError:
                return fn(target)
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _backlinks(req, path):
    index = req.world_index
    if index is None:
        return []
    rows = getattr(index, "backlinks", None)
    if isinstance(rows, dict):
        links = rows.get(path, ())
        output = []
        for source_path, link in links:
            source = _entry_at(index, source_path)
            context = ""
            if source is not None:
                raw = getattr(source, "raw", "") or ""
                span = getattr(link, "span", None)
                if span is not None:
                    start = _python_offset(raw, span.start)
                    end = _python_offset(raw, span.end)
                    left = max(raw.rfind("\n", 0, start), raw.rfind(". ", 0, start) + 1,
                               raw.rfind("? ", 0, start) + 1, raw.rfind("! ", 0, start) + 1)
                    boundaries = [pos for marker in ("\n", ". ", "? ", "! ")
                                  if (pos := raw.find(marker, end)) >= 0]
                    right = min(boundaries) if boundaries else len(raw)
                    context = raw[left:right].strip()
            output.append({"path": source_path,
                           "title": getattr(source, "title", os.path.basename(source_path)),
                           "link": asdict(link) if is_dataclass(link) else link,
                           "context": context})
        return output
    for method in ("backlinks", "get_backlinks"):
        fn = getattr(index, method, None)
        if callable(fn):
            try:
                result = fn(path)
                return result if result is not None else []
            except (KeyError, TypeError, ValueError):
                return []
    return []


def _python_offset(text, utf16_offset):
    units = 0
    for pos, char in enumerate(text):
        if units >= utf16_offset:
            return pos
        units += len(char.encode("utf-16-le")) // 2
    return len(text)


def _get_path(req):
    path = req.query.get("path", "")
    if not isinstance(path, str):
        raise InvalidPath("Path must be a string")
    return path


def status(req):
    """Cheap change detector: the generation of the current index snapshot."""
    if req.world_index is None:
        return _fail(404, "World vault is not enabled.")
    _ensure_index(req)
    return _ok("World status loaded.", {"generation": _generation(req)})


def tree(req):
    _ensure_index(req)
    path = _get_path(req)
    children = req.vault.ls(path)
    if children is None:
        return _fail(404, f"No such vault folder: {path}")
    rows = []
    for child in children:
        name = child.rsplit("/", 1)[-1]
        full = req.vault.resolve(child)
        if os.path.isdir(full):
            rows.append({"path": child, "name": name, "is_dir": True, "words": 0, "stub": False})
        else:
            text, _ = req.vault.read(child)
            item = parse(text, child)
            rows.append({"path": child, "name": name, "is_dir": False,
                         "words": item.words, "stub": item.stub})
    vault_id = hashlib.sha256(req.vault.root.encode("utf-8")).hexdigest()[:16]
    return _ok("Vault entries loaded.", {"path": path, "entries": rows,
                                        "vault_id": vault_id})


def get_entry(req):
    _ensure_index(req)
    path = _get_path(req)
    if not path:
        return _fail(400, "Which vault entry should I open?")
    text, revision = req.vault.read(path)
    item = parse(text, path, revision)
    story_diagnostics = []
    folders = getattr(req.world_index, "story_folders", ()) if req.world_index is not None else ()
    if any(path.startswith(folder + "/") for folder in folders):
        from world_story import parse_scene
        story_diagnostics = parse_scene(text)["diagnostics"]
    skipped = []
    html = render(item, lambda target: _resolve(req, target, path),
                  base_entries=_index_entries(req.world_index),
                  base_resolve=lambda target, source: _resolution(req, target, source),
                  skipped=skipped)
    links = []
    for link in item.links:
        row = asdict(link)
        resolution = _resolution(req, link.target, path)
        if isinstance(resolution, dict):
            row["resolved_path"] = resolution.get("path") or resolution.get("resolved_path")
            row["status"] = resolution.get("status", "resolved" if row["resolved_path"] else "unresolved")
            row["candidates"] = list(resolution.get("candidates", ()))
        else:
            row["resolved_path"] = getattr(resolution, "path", None)
            row["status"] = getattr(resolution, "status", "resolved" if row["resolved_path"] else "unresolved")
            row["candidates"] = list(getattr(resolution, "candidates", ()))
        links.append(row)
    return _ok("Vault entry loaded.", {
        "path": path, "text": text, "revision": revision,
        "entry": _entry_dict(item), "html": html, "links": links,
        "diagnostics": story_diagnostics,
        "backlinks": _backlinks(req, path),
        "skipped": skipped,
        "generation": _generation(req),
    })


def _search_index(index, query):
    if index is None:
        return None
    ensure = getattr(index, "ensure_ready", None)
    if callable(ensure):
        ensure()
    for method in ("search", "search_entries"):
        fn = getattr(index, method, None)
        if callable(fn):
            try:
                try:
                    result = fn(query, limit=MAX_RESULTS)
                except TypeError:
                    result = fn(query)
                return result if isinstance(result, list) else []
            except (TypeError, ValueError):
                return []
    return None


SNIPPET_CHARS = 120


def _snippet(body, query):
    """About SNIPPET_CHARS of plain text around the first match, or None.

    Returns {"snippet", "snippet_match": [start, end]}; the offsets point at
    the match inside the snippet so the client can emphasize it.
    """
    found = re.search(re.escape(query), body, re.IGNORECASE)
    if not found:
        return None
    room = max(0, SNIPPET_CHARS - len(found.group(0)))
    # Collapse whitespace on each side separately so the match offsets stay exact.
    before = " ".join(body[max(0, found.start() - room * 2):found.start()].split())
    after = " ".join(body[found.end():found.end() + room * 2].split())
    if body[found.start() - 1:found.start()].isspace():
        before += " "
    if body[found.end():found.end() + 1].isspace():
        after = " " + after
    lead = trail = ""
    if len(before) > room // 2:
        before = before[-(room // 2):]
        before = before.split(" ", 1)[1] if " " in before[:-1] else before
        lead = "…"
    elif found.start() > len(before) + room:
        lead = "…"
    if len(after) > room - len(before):
        after = after[:room - len(before)].rsplit(" ", 1)[0]
        trail = "…"
    start = len(lead) + len(before)
    text = lead + before + found.group(0) + after + trail
    return {"snippet": text, "snippet_match": [start, start + len(found.group(0))]}


def _annotate_search(index, results, query):
    """Adds `match` (title, alias or text), `matched_alias` and `snippet`."""
    entries = getattr(index, "entries", None) if index is not None else None
    needle = query.strip().casefold()
    if not needle or not isinstance(entries, dict):
        return results
    for row in results:
        entry = entries.get(row.get("path"))
        if entry is None or "match" in row:
            continue
        if needle in entry.title.casefold():
            row["match"] = "title"
            continue
        alias = next((a for a in entry.aliases if needle in a.casefold()), None)
        if alias is not None:
            row["match"], row["matched_alias"] = "alias", alias
            continue
        row["match"] = "text"
        snippet = _snippet(entry.body or "", query.strip())
        if snippet:
            row.update(snippet)
    return results


def search(req):
    query = req.query.get("q", "")
    if not isinstance(query, str):
        return _fail(400, "Search query must be text.")
    query = query.strip()
    results = _search_index(req.world_index, query)
    if results is not None:
        results = _annotate_search(req.world_index, results, query)
    if results is None:
        results = []
        needle = query.casefold()
        for path in req.vault.stat_all():
            text, _ = req.vault.read(path)
            item = parse(text, path)
            if not needle or needle in item.title.casefold() or any(needle in a.casefold() for a in item.aliases) or needle in item.body.casefold():
                results.append({"path": path, "title": item.title, "kind": item.kind,
                                "words": item.words, "stub": item.stub})
            if len(results) >= MAX_RESULTS:
                break
    return _ok("Search complete.", {"results": results[:MAX_RESULTS]})


def _graph_colors(vault):
    """Read Obsidian's path color groups without exposing arbitrary files."""
    root = os.path.realpath(vault.root)
    config = os.path.realpath(os.path.join(root, ".obsidian", "graph.json"))
    if not config.startswith(root + os.sep):
        return []
    try:
        with open(config, encoding="utf-8") as source:
            groups = json.load(source).get("colorGroups", [])
    except (OSError, ValueError, AttributeError, TypeError):
        return []
    result = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        query = group.get("query", "")
        color = group.get("color", {})
        if not isinstance(query, str) or not isinstance(color, dict):
            continue
        # Obsidian stores path filters as `path:Folder` or
        # `path:"Folder With Spaces"`. Other query forms are not guessed.
        match = re.fullmatch(r'\s*path:(?:"([^"]+)"|([^\s]+))\s*', query)
        rgb = color.get("rgb")
        if not match or not isinstance(rgb, int) or isinstance(rgb, bool) or not 0 <= rgb <= 0xFFFFFF:
            continue
        result.append((match.group(1) or match.group(2), rgb))
    return result


def graph(req):
    """Return all graph nodes or the resolved neighborhood of a note."""
    _ensure_index(req)
    index = req.world_index
    if index is None:
        return _fail(404, "World vault is not enabled.")
    around = req.query.get("around", "")
    depth_value = req.query.get("depth", "2")
    if not isinstance(around, str) or not isinstance(depth_value, str):
        return _fail(400, "Invalid graph filters.")
    try:
        depth = int(depth_value)
    except (TypeError, ValueError):
        return _fail(400, "Graph depth must be 1 or 2.")
    if depth not in (1, 2):
        return _fail(400, "Graph depth must be 1 or 2.")

    entries = getattr(index, "entries", {})
    if around and around not in entries:
        return _fail(400, "Around must be a canonical vault path.")

    from world_reports import is_world_entry
    story = tuple(getattr(index, "story_folders", ()) or ())
    colors = _graph_colors(req.vault) if req.vault is not None else []
    memberships = getattr(index, "memberships", {})
    nodes = {}
    for path, entry in sorted(entries.items()):
        rgb = next((value for prefix, value in colors
                    if path.casefold().startswith(prefix.casefold().rstrip("/") + "/") or
                    path.casefold() == prefix.casefold().rstrip("/")), None)
        biome_rows = memberships.get(path, ())
        nodes[path] = {
            "id": path, "path": path, "title": entry.title, "label": entry.title,
            "kind": entry.kind, "folder": entry.folder, "state": "entry",
            "world": is_world_entry(path, entry, story), "stub": entry.stub,
            "rework": "rework" in {tag.casefold() for tag in entry.tags},
            "inbound": len(getattr(index, "backlinks", {}).get(path, ())),
            "biomes": [{"path": row.path, "via": row.via}
                       for row in biome_rows],
            "color": f"#{rgb:06x}" if rgb is not None else None,
            "color_rgb": rgb,
        }

    edges = []
    for source_path in sorted(entries):
        for resolution in getattr(index, "forward_links", {}).get(source_path, ()):
            status = getattr(resolution, "status", "unresolved")
            target_path = getattr(resolution, "path", None)
            target_text = getattr(resolution, "target", "")
            candidates = list(getattr(resolution, "candidates", ()))
            if status == "resolved" and target_path in entries:
                target_id = target_path
            else:
                status = "ambiguous" if status == "ambiguous" else "unresolved"
                from urllib.parse import quote as quote_component
                target_id = f"{status}:{quote_component(target_text.casefold(), safe='')}"
                nodes.setdefault(target_id, {
                    "id": target_id, "path": None, "title": target_text,
                    "label": target_text, "kind": None, "folder": None,
                    "state": status, "world": None, "stub": False, "rework": False,
                    "inbound": 0, "biomes": [], "color": None,
                    "color_rgb": None,
                    "candidates": candidates if status == "ambiguous" else [],
                })
            edges.append({"source": source_path, "target": target_id,
                          "status": status, "label": target_text})

    if around:
        adjacency = {path: set() for path in entries}
        for edge in edges:
            if edge["status"] == "resolved":
                adjacency[edge["source"]].add(edge["target"])
                adjacency[edge["target"]].add(edge["source"])
        distances = {around: 0}
        frontier = [around]
        while frontier:
            current = frontier.pop(0)
            if distances[current] >= depth:
                continue
            for neighbor in sorted(adjacency[current]):
                if neighbor not in distances:
                    distances[neighbor] = distances[current] + 1
                    frontier.append(neighbor)
        selected = set(distances)
        edges = [edge for edge in edges if edge["source"] in selected and
                 (edge["status"] != "resolved" or edge["target"] in selected)]
        selected.update(edge["target"] for edge in edges if edge["status"] != "resolved")
        nodes = {node_id: node for node_id, node in nodes.items() if node_id in selected}

    return _ok("World graph loaded.", {
        "around": around or None, "depth": depth if around else None,
        "nodes": list(nodes.values()), "edges": edges,
        "generation": _generation(req),
    })


def tags(req):
    _ensure_index(req)
    names = {}
    index = req.world_index
    if index is not None:
        for name in getattr(index, "tags", {}):
            names.setdefault(name.casefold(), name)
        for entry in _index_entries(index):
            for name in getattr(entry, "tags", []):
                names.setdefault(name.casefold(), name)
    tags_path = "Tags.md"
    tags_full = req.vault.resolve(tags_path)
    if os.path.isfile(tags_full):
        text, _ = req.vault.read(tags_path)
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^#{1,6}\s", stripped):
                continue
            listed = re.match(r"^[-*+]\s+(.+)$", stripped)
            content = listed.group(1) if listed else stripped
            found = re.findall(r"(?<![\w])#([\w-]+)", content, re.UNICODE)
            if not found and listed:
                token = content.strip().strip("`*_")
                if re.fullmatch(r"[\w-]+", token, re.UNICODE):
                    found = [token]
            for name in found:
                names.setdefault(name.casefold(), name)
    values = sorted(names.values(), key=lambda name: (name.casefold(), name))
    return _ok("Tags loaded.", {"tags": values})


def _valid_text(value, label="Text"):
    if not isinstance(value, str):
        return False
    try:
        return len(value.encode("utf-8")) <= MAX_TEXT
    except UnicodeEncodeError:
        return False


def save_entry(req):
    body = req.body
    path, text, revision = body.get("path"), body.get("text"), body.get("revision")
    if not isinstance(path, str) or not path:
        return _fail(400, "Entry path is required.")
    if not _valid_text(text):
        return _fail(400, "Entry text must be a string under one megabyte.")
    if not isinstance(revision, str) or not revision:
        return _fail(400, "Entry revision is required.")
    replace_revision = body.get("replace_revision")
    if replace_revision is not None and (not isinstance(replace_revision, str) or not replace_revision):
        return _fail(400, "Replacement revision must be a nonempty string.")
    try:
        result = req.vault.write(path, text, revision, replace_revision)
    except RevisionConflict as error:
        return _fail(409, str(error), {"text": error.current_text, "revision": error.current_revision})
    if "recovery_path" in result:
        result["recovery"] = result["recovery_path"]
    invalidate = getattr(req.world_index, "invalidate", None)
    if callable(invalidate):
        invalidate()
        # Rebuild now so the reported generation is the one that includes
        # this write.
        _ensure_index(req)
    result = dict(result, generation=_generation(req))
    return _ok("Entry saved.", result)


def _create_source_path(target):
    return target[:-3] if target.lower().endswith(".md") else target


def _render_new_text(body):
    template_path = body.get("template", "")
    if template_path is None:
        template_path = ""
    if not isinstance(template_path, str):
        raise ValueError("Template must be a vault path.")
    initial_body = body.get("body", "")
    if not _valid_text(initial_body):
        raise ValueError("Entry text must be a string under one megabyte.")
    lines = []
    from_targets = body.get("from_targets", [])
    if not isinstance(from_targets, list) or any(not isinstance(p, str) or not p for p in from_targets):
        raise ValueError("from_targets must be a list of canonical vault paths.")
    if from_targets:
        links = [f"[[{_create_source_path(p)}]]" for p in from_targets]
        lines.append("From: " + " ".join(links))
    origin = body.get("origin", [])
    # A seed may carry its meaning in the same lossless syntax the parser
    # understands, for example ``rainseed (a lantern made by rain)``.
    origin_pattern = r"[^\s,()\r\n]+(?:\s+\([^\r\n]*\))?"
    if not isinstance(origin, list) or any(not isinstance(word, str) or not re.fullmatch(origin_pattern, word.strip()) for word in origin):
        raise ValueError("origin must contain seed words, optionally followed by a parenthesized gloss.")
    if origin:
        lines.append("Origin: " + " ".join(origin))
    # Supported header directives must be consecutive for the parser to
    # recognize them on a create/open round trip.  Tags are body content.
    tags = body.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not re.fullmatch(r"[\w-]+", tag.lstrip("#"), re.UNICODE) for tag in tags):
        raise ValueError("tags must be a list of nonempty strings.")
    if tags:
        lines.append(" ".join("#" + tag.lstrip("#") for tag in tags))
    template = ""
    if template_path:
        # Caller resolves and reads the template after validation by the vault.
        template = body.get("_template_text", "")
        if not isinstance(template, str):
            raise ValueError("Template contents are invalid.")
        if len(template.encode("utf-8")) > MAX_TEXT:
            raise ValueError("Template must be under one megabyte.")
    if template:
        if lines: lines.append("")
        lines.extend(template.splitlines())
    text = "\n".join(lines)
    if initial_body:
        if text.rstrip():
            text = text.rstrip("\n") + "\n\n"
        text += initial_body
    if text and not text.endswith("\n"):
        text += "\n"
    if not _valid_text(text):
        raise ValueError("Created entry must be under one megabyte.")
    return text


def create_entry(req):
    body = req.body
    idea = body.get("idea")
    if idea is not None and (not isinstance(idea, dict) or
            not isinstance(idea.get("path"), str) or
            not isinstance(idea.get("revision"), str) or
            not isinstance(idea.get("start"), int) or isinstance(idea.get("start"), bool) or
            not isinstance(idea.get("end"), int) or isinstance(idea.get("end"), bool) or
            not isinstance(idea.get("expected"), str)):
        return _fail(400, "Idea reference must include its path, revision, exact span and text.")
    folder, title = body.get("folder", ""), body.get("title")
    if not isinstance(folder, str) or not isinstance(title, str) or not title.strip():
        return _fail(400, "A folder and entry title are required.")
    title = title.strip()
    if title in (".", "..") or "/" in title or "\\" in title or title.startswith("."):
        return _fail(400, "Entry title must be a single visible filename.")
    path = (folder + "/" if folder else "") + title + ".md"
    try:
        folder_full = req.vault.resolve(folder)
        if not os.path.isdir(folder_full):
            return _fail(400, "Entry folder must be an existing vault folder.")
        from_targets = body.get("from_targets", [])
        if not isinstance(from_targets, list):
            return _fail(400, "from_targets must be a list of canonical vault paths.")
        for target in from_targets:
            if not isinstance(target, str) or not target.lower().endswith(".md"):
                return _fail(400, "Each source must be a canonical Markdown note path.")
            full = req.vault.resolve(target)
            if req.vault.relative(full) != target or not os.path.isfile(full):
                return _fail(400, "Each source must be an existing canonical vault note path.")
            req.vault.read(target)
        template_path = body.get("template", "")
        if template_path is None:
            template_path = ""
        if template_path:
            if (not isinstance(template_path, str) or
                    not template_path.startswith("Templates/") or
                    not template_path.lower().endswith(".md")):
                return _fail(400, "Template must be a Markdown path under Templates/.")
            template_full = req.vault.resolve(template_path)
            if req.vault.relative(template_full) != template_path or not os.path.isfile(template_full):
                return _fail(400, "Template must be an existing canonical vault note path.")
            template_text, _ = req.vault.read(template_path)
            body = dict(body, _template_text=template_text)
        text = _render_new_text(body)
    except ValueError as error:
        return _fail(400, str(error))
    except UnreadableSource as error:
        return _fail(400, str(error))
    try:
        result = req.vault.create(path, text)
    except DestinationConflict as error:
        return _fail(409, str(error), {"path": error.existing_path})
    if idea is not None:
        from world_backlog import IdeaSpanMismatch, strike_idea
        try:
            update = strike_idea(req.vault, idea["path"], idea["revision"],
                                 idea["start"], idea["end"], idea["expected"])
            result["idea_updated"] = True
            result["idea_revision"] = update["revision"]
        except (RevisionConflict, IdeaSpanMismatch, InvalidPath, UnreadableSource) as error:
            # Creation cannot be rolled back safely: report the separate idea
            # update explicitly so the user can review and retry it.
            result["idea_updated"] = False
            result["idea_error"] = str(error)
    invalidate = getattr(req.world_index, "invalidate", None)
    if callable(invalidate):
        invalidate()
        _ensure_index(req)
    result = dict(result, generation=_generation(req))
    return _ok("Entry created.", result)


def create_folder(req):
    """Create an empty child folder below an existing vault directory."""
    parent, name = req.body.get("parent", ""), req.body.get("name")
    if not isinstance(parent, str) or not isinstance(name, str):
        return _fail(400, "A parent folder and folder name are required.")
    name = name.strip()
    if (not name or name in (".", "..") or "/" in name or "\\" in name
            or name.startswith(".")):
        return _fail(400, "Folder name must be a single visible filename.")
    path = (parent + "/" if parent else "") + name
    try:
        parent_full = req.vault.resolve(parent)
        if req.vault.relative(parent_full) != parent or not os.path.isdir(parent_full):
            return _fail(400, "Parent folder must be an existing canonical vault folder.")
        result = req.vault.create_folder(path)
    except InvalidPath as error:
        return _fail(400, str(error))
    except UnreadableSource as error:
        return _fail(400, str(error))
    except FolderConflict as error:
        return _fail(409, str(error), {"path": error.existing_path})
    invalidate = getattr(req.world_index, "invalidate", None)
    if callable(invalidate):
        invalidate()
    return _ok("Folder created.", result)


def backlog(req):
    from world_backlog import list_ideas
    _ensure_index(req)
    return _ok("Ideas loaded.", {"ideas": list_ideas(req.vault),
                                 "generation": _generation(req)})


def strike_idea_route(req):
    from world_backlog import IdeaSpanMismatch, strike_idea
    body = req.body
    if (not isinstance(body.get("path"), str) or
            not isinstance(body.get("revision"), str) or
            not isinstance(body.get("start"), int) or isinstance(body.get("start"), bool) or
            not isinstance(body.get("end"), int) or isinstance(body.get("end"), bool) or
            not isinstance(body.get("expected"), str)):
        return _fail(400, "Idea path, revision, exact span and text are required.")
    try:
        result = strike_idea(req.vault, body["path"], body["revision"],
                             body["start"], body["end"], body["expected"])
    except RevisionConflict as error:
        return _fail(409, str(error), {"text": error.current_text,
                                      "revision": error.current_revision})
    except IdeaSpanMismatch as error:
        return _fail(409, str(error))
    return _ok("Idea marked as started.", result)


def nearby(req):
    text, path, revision = req.body.get("text"), req.body.get("path", ""), req.body.get("client_revision")
    if not _valid_text(text):
        return _fail(400, "Draft text must be a string under one megabyte.")
    if not isinstance(path, str) or not isinstance(revision, (str, int)):
        return _fail(400, "Draft path and client revision are required.")
    item = parse(text, path or "Draft.md")
    _ensure_index(req)
    skipped = []
    html = render(item, lambda target: _resolve(req, target, item.path),
                  base_entries=_index_entries(req.world_index),
                  base_resolve=lambda target, source: _resolution(req, target, source),
                  skipped=skipped)
    groups = {"named_not_linked": [], "same_biome": [], "same_tags": [],
              "talks_about_same_things": [], "linked_from_what_you_link": []}
    merged = []
    index = req.world_index
    if index is not None:
        from nearby import suggest
        try:
            supplied = suggest(item, index, revision,
                               _dismissed(req, "target"))
            for key, cards in supplied["groups"].items():
                if isinstance(cards, list):
                    groups[key] = cards
            merged = supplied["merged"]
        except (TypeError, ValueError):
            pass
    # Templates and the root tag index are structural notes.
    def structural(card):
        return isinstance(card, dict) and (
            card.get("path") == "Tags.md" or
            str(card.get("path", "")).startswith("Templates/"))
    for key, cards in groups.items():
        if isinstance(cards, list):
            groups[key] = [card for card in cards if not structural(card)]
    merged = [card for card in merged if not structural(card)]
    # The editor needs a parsed view of its unsaved draft without receiving a
    # second copy of the raw note.  Keep this deliberately to supported
    # structured fields so the client can show a live summary safely.
    metadata = {
        "from_targets": [asdict(link) for link in item.from_targets],
        "origin": item.origin, "glosses": item.glosses, "themes": item.themes,
        "aliases": item.aliases, "tags": item.tags, "notes": item.notes,
    }
    return _ok("Draft preview ready.", {"client_revision": revision, "html": html,
                                         "skipped": skipped, "groups": groups,
                                         "merged": merged, "metadata": metadata,
                                         "generation": _generation(req)})


def matrix(req):
    _ensure_index(req)
    from world_reports import coverage_matrix
    return _ok("Coverage loaded.", coverage_matrix(req.world_index) |
               {"generation": _generation(req)})


def placement(req):
    """Folder, From and template for a place and/or kind picked on the create screen.

    A bare request returns only ``kinds``; the other fields are null.
    """
    _ensure_index(req)
    from world_reports import placement as place, world_kinds
    origin, kind = req.query.get("from"), req.query.get("kind")
    for value in (origin, kind):
        if value is not None and (not isinstance(value, str) or len(value) > 1000):
            return _fail(400, "`from` and `kind` must be short text.")
    origin, kind = origin or None, kind or None
    # With neither, the answer is just the kinds (the create screen's chips).
    if kind is not None and kind not in world_kinds(req.world_index):
        return _fail(400, f"Unknown kind: {kind}")
    if origin is not None and _entry_at(req.world_index, origin) is None:
        return _fail(404, f"No such entry: {origin}")
    return _ok("Placement ready.", place(req.world_index, origin, kind))


def _dismissed(req, kind):
    """Dismissed keys of one kind for this request's world."""
    from world_triage import store_for_request
    store = store_for_request(req)
    return store.keys(kind) if store is not None else frozenset()


def _dismissal_counts(req, **kinds):
    """How many dismissals of each named group of kinds the store holds.

    ``_dismissed`` and ``split_dismissed`` count the *rows* a dismissal hides;
    this counts the dismissals themselves, so the UI can say both.
    """
    from world_triage import store_for_request
    store = store_for_request(req)
    found = store.dismissed() if store is not None else []
    return {name: sum(1 for row in found if row["kind"] in group)
            for name, group in kinds.items()}


def _with_triage(rows, kind, key_of):
    """Tag rows with the ``triage`` kind and key the UI sends to dismiss them."""
    return [dict(row, triage={"kind": kind, "key": key_of(row)}) for row in rows]


def health(req):
    _ensure_index(req)
    from world_reports import health_report, mention_counts
    from world_triage import (drift_row_key, mention_row_key, name_key,
                              normalize_key, split_dismissed)
    sections = health_report(req.world_index)
    from world_names import names_without_entries
    names = names_without_entries(req.world_index)
    from world_lexicon import WorldLexicon
    lexicon = WorldLexicon(req.world_index, req.fm, req.word_index).query()
    entries_by_word = {row["word"]: row for row in lexicon["entries"]}
    uses = {word: row["uses"] for word, row in entries_by_word.items()}
    drift = []
    for row in lexicon["drift"]:
        if not (uses.get(row["from"]) and uses.get(row["to"])):
            continue
        item = {**row, "path": uses[row["from"]][0]["path"],
                "other_path": uses[row["to"]][0]["path"]}
        for side, word in (("from", row["from"]), ("to", row["to"])):
            if "which" in entries_by_word[word]:
                item[side + "_which"] = entries_by_word[word]["which"]
        drift.append(item)
    dismissed_words = _dismissed(req, "word")
    names, names_hidden = split_dismissed(
        names, _dismissed(req, "name"), name_key)
    drift, drift_hidden = split_dismissed(
        drift, _dismissed(req, "drift"), drift_row_key,
        extra=lambda row: (normalize_key("word", row["from"]) in dismissed_words or
                           normalize_key("word", row["to"]) in dismissed_words))
    dismissed_targets = _dismissed(req, "target")
    mentions, mentions_hidden = split_dismissed(
        sections["unlinked_mentions"], _dismissed(req, "mention"), mention_row_key,
        extra=lambda row: row["target_path"] in dismissed_targets)
    # A common word (Despite, Water) is flagged, not dropped: the page hides it
    # by default but can still show it. The dictionary is the lexicon's own.
    from world_lexicon import _dictionary, _key
    common = _dictionary(req.fm) if req.fm is not None else frozenset()
    names = [dict(row, common=len(row["phrase"].split()) == 1 and
                  _key(row["phrase"]) in common) for row in names]
    sections["names_without_entry"] = _with_triage(names, "name", name_key)
    sections["spelling_drift"] = _with_triage(drift, "drift", drift_row_key)
    sections["unlinked_mentions"] = [
        dict(row, target_triage={"kind": "target", "key": row["target_path"]})
        for row in _with_triage(mentions, "mention", mention_row_key)]
    # The section keeps every row so the UI can reveal the rest; the headline
    # count is the rows worth acting on.
    counts = {key: len(rows) for key, rows in sections.items()}
    counts["unlinked_mentions"] = sum(1 for row in mentions if row["actionable"])
    counts["unlinked_mentions_all"] = len(mentions)
    return _ok("Upkeep loaded.", {
        "sections": sections,
        "counts": counts,
        "mention_counts": mention_counts(mentions),
        "dismissed": {"names_without_entry": names_hidden,
                      "spelling_drift": drift_hidden,
                      "unlinked_mentions": mentions_hidden},
        "dismissals": _dismissal_counts(
            req, names_without_entry=("name",), spelling_drift=("drift",),
            unlinked_mentions=("mention", "target")),
        "generation": _generation(req),
    })


def _triage_payload(store):
    rows = [{"kind": row["kind"], "key": row["key"], "dismissed_at": row["at"]}
            for row in store.dismissed()]
    counts = {}
    from world_triage import KINDS
    for kind in KINDS:
        counts[kind] = sum(1 for row in rows if row["kind"] == kind)
    return {"dismissals": rows, "counts": counts}


def triage_list(req):
    from world_triage import store_for_request
    store = store_for_request(req)
    if store is None:
        return _fail(404, "World vault is not enabled.")
    return _ok("Dismissals loaded.", _triage_payload(store))


def triage_update(req):
    from world_triage import store_for_request, validate
    store = store_for_request(req)
    if store is None:
        return _fail(404, "World vault is not enabled.")
    action, kind, key = (req.body.get("action"), req.body.get("kind"),
                         req.body.get("key"))
    if action not in ("dismiss", "restore"):
        return _fail(400, "Action must be dismiss or restore.")
    problem = validate(kind, key)
    if problem:
        return _fail(400, problem)
    try:
        changed = (store.dismiss if action == "dismiss" else store.restore)(kind, key)
    except OSError:
        return _fail(500, "Could not save the dismissal.")
    message = ("Dismissed." if action == "dismiss" else "Restored.")
    return _ok(message, dict(_triage_payload(store), changed=changed))


def lexicon(req):
    _ensure_index(req)
    from world_lexicon import WorldLexicon
    from world_triage import drift_row_key, normalize_key, split_dismissed
    query = req.query.get("q", "")
    biome = req.query.get("biome", "")
    once = req.query.get("once", "")
    if (not isinstance(query, str) or len(query) > 100 or
            not isinstance(biome, str) or len(biome) > 500 or
            once not in ("", "0", "1", "false", "true")):
        return _fail(400, "Invalid lexicon filters.")
    if biome and (biome not in req.world_index.entries or
                  not biome.startswith("Locations/Biomes/")):
        return _fail(400, "Biome must be a canonical biome path.")
    data = WorldLexicon(req.world_index, req.fm, req.word_index).query(
        q=query, biome=biome or None, once=once in ("1", "true"))
    words = _dismissed(req, "word")
    entries, entries_hidden = split_dismissed(
        data["entries"], words, lambda row: normalize_key("word", row["word"]))
    drift, drift_hidden = split_dismissed(
        data["drift"], _dismissed(req, "drift"), drift_row_key,
        extra=lambda row: (normalize_key("word", row["from"]) in words or
                           normalize_key("word", row["to"]) in words))
    data["entries"] = _with_triage(entries, "word", lambda row: row["word"])
    data["drift"] = _with_triage(drift, "drift", drift_row_key)
    for row in data["drift"]:
        row["paths"] = list(dict.fromkeys(
            row.get("from_paths", ()) + row.get("to_paths", ())))
    data["dismissed"] = {"entries": entries_hidden, "drift": drift_hidden}
    data["dismissals"] = _dismissal_counts(req, entries=("word",), drift=("drift",))
    data["biomes"] = [{"path": path, "title": entry.title}
                      for path, entry in sorted(req.world_index.entries.items())
                      if path.startswith("Locations/Biomes/")]
    data["generation"] = _generation(req)
    return _ok("Lexicon loaded.", data)


def roll(req):
    _ensure_index(req)
    from nearby import link_target
    from world_roller import roll as make_roll
    body = req.body
    facet = body.get("facet")
    entry = body.get("entry")
    words = body.get("words")
    if facet is not None and (not isinstance(facet, str) or not facet.strip()):
        return _fail(400, "Facet must be nonempty text.")
    if entry is not None and (not isinstance(entry, str) or not entry):
        return _fail(400, "Entry must be a canonical vault path.")
    if words is not None and (not isinstance(words, list) or len(words) != 2 or
                              any(not isinstance(word, str) or not word for word in words)):
        return _fail(400, "Words must be exactly two nonempty strings.")
    try:
        cheat_sheet, _ = req.vault.read("How-To.md")
        active_words = req.session.active_words()
        result = make_roll(req.world_index.entries, req.world_index.backlinks,
                           active_words, cheat_sheet, facet=facet, entry=entry,
                           words=words,
                           direct_places=getattr(req.world_index, "direct_places", None),
                           link_of=lambda path: link_target(req.world_index, path),
                           story_folders=getattr(req.world_index, "story_folders", ()))
    except ValueError as error:
        return _fail(400, str(error))
    return _ok("Prompt rolled.", result)


def story(req):
    _ensure_index(req)
    from world_story import report
    data = report(req.world_index, getattr(req.world_index, "story_folders", ()))
    return _ok("Story report loaded.", dict(data, generation=_generation(req)))


def quotes(req):
    _ensure_index(req)
    from world_story import quotes as story_quotes
    by = req.query.get("by", "")
    if not isinstance(by, str):
        return _fail(400, "Quotation speaker must be a canonical vault path.")
    try:
        return _ok("Quotations loaded.", story_quotes(req.world_index, by or None))
    except ValueError as error:
        return _fail(400, str(error))


def export(req):
    _ensure_index(req)
    from world_story import export as make_export
    path = req.query.get("path", "story")
    if not isinstance(path, str) or len(path) > 1000:
        return _fail(400, "Export path must be a vault folder or `story`.")
    try:
        return _ok("Export ready.", make_export(req.world_index,
                                                  getattr(req.world_index, "story_folders", ()), path))
    except ValueError as error:
        return _fail(400, str(error))


def _generation(req):
    """The index generation behind a response, or None without an index."""
    return getattr(req.world_index, "generation", None) if req.world_index is not None else None


def _ensure_index(req):
    ensure = getattr(req.world_index, "ensure_ready", None) if req.world_index is not None else None
    if callable(ensure):
        ensure()


ROUTES = {
    ("GET", "/api/world/status"): status,
    ("GET", "/api/world/tree"): tree,
    ("GET", "/api/world/entry"): get_entry,
    ("GET", "/api/world/search"): search,
    ("GET", "/api/world/graph"): graph,
    ("GET", "/api/world/tags"): tags,
    ("POST", "/api/world/entry"): save_entry,
    ("POST", "/api/world/new"): create_entry,
    ("POST", "/api/world/folder"): create_folder,
    ("GET", "/api/world/backlog"): backlog,
    ("POST", "/api/world/backlog/strike"): strike_idea_route,
    ("POST", "/api/world/nearby"): nearby,
    ("GET", "/api/world/matrix"): matrix,
    ("GET", "/api/world/placement"): placement,
    ("GET", "/api/world/health"): health,
    ("GET", "/api/world/lexicon"): lexicon,
    ("GET", "/api/world/triage"): triage_list,
    ("POST", "/api/world/triage"): triage_update,
    ("POST", "/api/world/roll"): roll,
    ("GET", "/api/world/story"): story,
    ("GET", "/api/world/quotes"): quotes,
    ("GET", "/api/world/export"): export,
}


def dispatch(req):
    handler = ROUTES.get((req.method, req.path))
    if handler is None:
        return _fail(404, f"No such endpoint: {req.method} {req.path}")
    try:
        return handler(req)
    except (InvalidPath, UnreadableSource) as error:
        return _fail(400, str(error))
