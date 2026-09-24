"""HTTP routes for the optional worldbuilding vault."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import os
import re
from urllib.parse import quote

from entry import parse, render
from vault import (DestinationConflict, InvalidPath, RevisionConflict,
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
    return _ok("Vault entries loaded.", {"path": path, "entries": rows})


def get_entry(req):
    _ensure_index(req)
    path = _get_path(req)
    if not path:
        return _fail(400, "Which vault entry should I open?")
    text, revision = req.vault.read(path)
    item = parse(text, path, revision)
    html = render(item, lambda target: _resolve(req, target, path))
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
        "backlinks": _backlinks(req, path),
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


def search(req):
    query = req.query.get("q", "")
    if not isinstance(query, str):
        return _fail(400, "Search query must be text.")
    query = query.strip()
    results = _search_index(req.world_index, query)
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
    return _ok("Entry saved.", result)


def _create_source_path(target):
    return target[:-3] if target.lower().endswith(".md") else target


def _render_new_text(body):
    template_path = body.get("template", "")
    if template_path is None:
        template_path = ""
    if not isinstance(template_path, str):
        raise ValueError("Template must be a vault path.")
    lines = []
    from_targets = body.get("from_targets", [])
    if not isinstance(from_targets, list) or any(not isinstance(p, str) or not p for p in from_targets):
        raise ValueError("from_targets must be a list of canonical vault paths.")
    if from_targets:
        links = [f"[[{_create_source_path(p)}]]" for p in from_targets]
        lines.append("From: " + " ".join(links))
    tags = body.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not re.fullmatch(r"[\w-]+", tag.lstrip("#"), re.UNICODE) for tag in tags):
        raise ValueError("tags must be a list of nonempty strings.")
    if tags:
        lines.append(" ".join("#" + tag.lstrip("#") for tag in tags))
    origin = body.get("origin", [])
    if not isinstance(origin, list) or any(not isinstance(word, str) or not re.fullmatch(r"[^\s\r\n]+", word) for word in origin):
        raise ValueError("origin must be a list of nonempty strings.")
    if origin:
        lines.append("Origin: " + " ".join(origin))
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
    if text and not text.endswith("\n"):
        text += "\n"
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
    return _ok("Entry created.", result)


def backlog(req):
    from world_backlog import list_ideas
    return _ok("Ideas loaded.", {"ideas": list_ideas(req.vault)})


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


def _nearby_groups(req, item):
    result = {"named_not_linked": [], "same_biome": [], "same_tags": []}
    candidates = _index_entries(req.world_index)
    linked = {link.target.casefold() for link in item.links}
    draft = item.body.casefold()
    for other in candidates:
        other_path = getattr(other, "path", None) or (other.get("path") if isinstance(other, dict) else None)
        other_title = getattr(other, "title", None) or (other.get("title") if isinstance(other, dict) else None)
        other_aliases = getattr(other, "aliases", []) or (other.get("aliases", []) if isinstance(other, dict) else [])
        other_tags = getattr(other, "tags", []) or (other.get("tags", []) if isinstance(other, dict) else [])
        if not other_path or other_path == item.path or not other_title:
            continue
        names = [other_title] + list(other_aliases)
        if any(name.casefold() not in linked and re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", draft) for name in names):
            result["named_not_linked"].append({"path": other_path, "title": other_title})
        overlap = sorted(set(item.tags) & set(other_tags))
        if overlap:
            result["same_tags"].append({"path": other_path, "title": other_title, "tags": overlap})
    return result


def nearby(req):
    text, path, revision = req.body.get("text"), req.body.get("path", ""), req.body.get("client_revision")
    if not _valid_text(text):
        return _fail(400, "Draft text must be a string under one megabyte.")
    if not isinstance(path, str) or not isinstance(revision, (str, int)):
        return _fail(400, "Draft path and client revision are required.")
    item = parse(text, path or "Draft.md")
    _ensure_index(req)
    html = render(item, lambda target: _resolve(req, target, item.path))
    groups = _nearby_groups(req, item)
    index = req.world_index
    fn = None
    if index is not None:
        try:
            from nearby import suggestions
            fn = lambda draft: suggestions(draft, index, revision)
        except ImportError:
            fn = getattr(index, "nearby", None)
    if callable(fn):
        try:
            supplied = fn(item)
            if isinstance(supplied, dict):
                for key, cards in supplied.items():
                    if isinstance(cards, list):
                        groups[key] = cards
        except (TypeError, ValueError):
            pass
    return _ok("Draft preview ready.", {"client_revision": revision, "html": html, "groups": groups})


def matrix(req):
    _ensure_index(req)
    from world_reports import coverage_matrix
    return _ok("Coverage loaded.", coverage_matrix(req.world_index))


def health(req):
    _ensure_index(req)
    from world_reports import health_report
    sections = health_report(req.world_index)
    from world_names import names_without_entries
    sections["names_without_entry"] = names_without_entries(req.world_index)
    from world_lexicon import WorldLexicon
    lexicon = WorldLexicon(req.world_index, req.fm).query()
    uses = {row["word"]: row["uses"] for row in lexicon["entries"]}
    sections["spelling_drift"] = [
        {**row, "path": uses[row["from"]][0]["path"],
         "other_path": uses[row["to"]][0]["path"]}
        for row in lexicon["drift"]
        if uses.get(row["from"]) and uses.get(row["to"])
    ]
    return _ok("Upkeep loaded.", {"sections": sections,
                                  "counts": {key: len(rows) for key, rows in sections.items()}})


def lexicon(req):
    _ensure_index(req)
    from world_lexicon import WorldLexicon
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
    for row in data["drift"]:
        row["paths"] = list(dict.fromkeys(
            row.get("from_paths", ()) + row.get("to_paths", ())))
    data["biomes"] = [{"path": path, "title": entry.title}
                      for path, entry in sorted(req.world_index.entries.items())
                      if path.startswith("Locations/Biomes/")]
    return _ok("Lexicon loaded.", data)


def roll(req):
    _ensure_index(req)
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
                           words=words)
    except ValueError as error:
        return _fail(400, str(error))
    return _ok("Prompt rolled.", result)


def _ensure_index(req):
    ensure = getattr(req.world_index, "ensure_ready", None) if req.world_index is not None else None
    if callable(ensure):
        ensure()


ROUTES = {
    ("GET", "/api/world/tree"): tree,
    ("GET", "/api/world/entry"): get_entry,
    ("GET", "/api/world/search"): search,
    ("GET", "/api/world/tags"): tags,
    ("POST", "/api/world/entry"): save_entry,
    ("POST", "/api/world/new"): create_entry,
    ("GET", "/api/world/backlog"): backlog,
    ("POST", "/api/world/backlog/strike"): strike_idea_route,
    ("POST", "/api/world/nearby"): nearby,
    ("GET", "/api/world/matrix"): matrix,
    ("GET", "/api/world/health"): health,
    ("GET", "/api/world/lexicon"): lexicon,
    ("POST", "/api/world/roll"): roll,
}


def dispatch(req):
    handler = ROUTES.get((req.method, req.path))
    if handler is None:
        return _fail(404, f"No such endpoint: {req.method} {req.path}")
    try:
        return handler(req)
    except (InvalidPath, UnreadableSource) as error:
        return _fail(400, str(error))
