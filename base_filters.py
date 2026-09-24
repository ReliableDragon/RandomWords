"""Small, deliberately bounded evaluator for the vault's Base filters."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FilterResult:
    supported: bool
    paths: tuple[str, ...] = ()
    diagnostic: str | None = None


_LINK = re.compile(r"file\.links\.contains\(this\.file\.name\)")
_PATH = re.compile(r'''file\.path\.contains\((?:"([^"\n]*)"|'([^'\n]*)')\)''')


def _indent(line: str) -> tuple[int, str]:
    # Obsidian templates contain tabs alongside spaces. Treat each tab as four
    # columns, matching the indentation used elsewhere in the vault.
    prefix = line[:len(line) - len(line.lstrip(" \t"))]
    return len(prefix.expandtabs(4)), line[len(prefix):].strip()


def _parse_filter(lines: list[str]):
    """Parse the YAML-like and/or subset into tuples; return None if unknown."""
    rows = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent, text = _indent(line)
        if text == "filters:":
            continue
        if text.startswith("views:"):
            break
        rows.append((indent, text))
    if not rows:
        return None

    def parse_children(pos: int, parent_indent: int):
        children = []
        while pos < len(rows) and rows[pos][0] > parent_indent:
            indent, text = rows[pos]
            if text.startswith("- "):
                text = text[2:].strip()
            if text in ("and:", "or:"):
                op = text[:-1]
                pos += 1
                nested, pos = parse_children(pos, indent)
                if not nested:
                    return None, pos
                children.append((op, nested))
                continue
            if _LINK.fullmatch(text):
                children.append(("link", None))
                pos += 1
                continue
            path_match = _PATH.fullmatch(text)
            if path_match:
                children.append(("path", path_match.group(1) or path_match.group(2)))
                pos += 1
                continue
            return None, pos
        return children, pos

    # Find the children beneath filters: while allowing top-level `and` as a
    # root expression. Other top-level Base settings are deliberately ignored.
    try:
        filters_at = next(i for i, (_, text) in enumerate(rows) if text == "filters:")
    except StopIteration:
        filters_at = -1
    if filters_at >= 0:
        del rows[filters_at]
    if not rows:
        return None
    children, pos = parse_children(0, -1)
    if children is None or pos != len(rows):
        return None
    # Unwrap a one-child root `and`/`or`; otherwise a filter list is AND.
    if len(children) == 1 and children[0][0] in ("and", "or"):
        return children[0]
    return ("and", children)


def evaluate(source: str, current, entries, resolve_link=None) -> FilterResult:
    """Evaluate supported filters against entries. Input is never executed."""
    ast = _parse_filter(source.splitlines())
    if ast is None:
        return FilterResult(False, diagnostic="Unsupported Base filter expression")
    current_name = getattr(current, "title", "")

    def test(node, candidate):
        op, value = node
        if op == "link":
            for link in getattr(candidate, "links", ()):
                target = getattr(link, "target", "")
                if resolve_link is not None:
                    resolution = resolve_link(target, getattr(candidate, "path", ""))
                    resolved = (resolution if isinstance(resolution, str) else
                                resolution.get("path") or resolution.get("resolved_path")
                                if isinstance(resolution, dict) else
                                getattr(resolution, "path", None) or getattr(resolution, "resolved_path", None))
                    status = (resolution.get("status") if isinstance(resolution, dict)
                              else getattr(resolution, "status", None))
                    if resolved:
                        if resolved == getattr(current, "path", ""):
                            return True
                        continue
                    if resolution is not None and status in ("ambiguous", "unresolved"):
                        continue
                    if resolve_link is not None and resolution is not None:
                        continue
                if target.rsplit("/", 1)[-1].casefold() == current_name.casefold():
                    return True
            return False
        if op == "path":
            return value.casefold() in getattr(candidate, "path", "").casefold()
        outcomes = [test(child, candidate) for child in value]
        return all(outcomes) if op == "and" else any(outcomes)

    matched = tuple(sorted((getattr(entry, "path", "") for entry in entries
                            if getattr(entry, "path", "") != getattr(current, "path", "") and test(ast, entry)),
                           key=str.casefold))
    return FilterResult(True, matched)
