"""Offsets in the coordinates the browser's editor uses."""
from __future__ import annotations

from bisect import bisect_left
import re


_ASTRAL = re.compile("[\U00010000-\U0010ffff]")


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def editor_offset(text: str, offset: int) -> int:
    """UTF-16 offset of ``text[offset]`` after a textarea's newline normalization.

    Notes keep their ``\\r\\n`` on disk, but the editor holds ``\\n`` only, so
    any span sent to it must not count the carriage returns before it.
    """
    prefix = text[:offset].replace("\r\n", "\n").replace("\r", "\n")
    return utf16_length(prefix)


def editor_offsets(text: str):
    """``editor_offset`` for one ``text``, in O(log n) per offset.

    A ``\\r\\n`` pair is one editor character once its ``\\n`` is before the
    offset, and a character outside the Basic Multilingual Plane is two.
    """
    pairs = [match.end() - 1 for match in re.finditer("\r\n", text)]
    astral = [match.start() for match in _ASTRAL.finditer(text)]
    return lambda offset: (offset - bisect_left(pairs, offset)
                           + bisect_left(astral, offset))
