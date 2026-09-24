"""Revision-safe listing and completion of Ideas vault bullets."""

from __future__ import annotations

import re

from vault import InvalidPath, RevisionConflict


_BULLET = re.compile(r'^(?P<prefix>[ \t]*[-*+][ \t]+)(?P<body>.*)$')


class IdeaSpanMismatch(ValueError):
  """The supplied UTF-16 span no longer identifies the expected idea text."""


def _utf16_length(value: str) -> int:
  return len(value.encode('utf-16-le')) // 2


def _codepoint_offset(text: str, utf16_offset: int) -> int:
  if not isinstance(utf16_offset, int) or isinstance(utf16_offset, bool) or utf16_offset < 0:
    raise IdeaSpanMismatch('Idea offsets must be nonnegative UTF-16 positions.')
  units = 0
  for index, char in enumerate(text):
    if units == utf16_offset:
      return index
    units += _utf16_length(char)
    if units > utf16_offset:
      raise IdeaSpanMismatch('Idea offset splits a UTF-16 character.')
  if units == utf16_offset:
    return len(text)
  raise IdeaSpanMismatch('Idea offset is outside the note.')


def _idea_rows(path: str, text: str, revision: str) -> list[dict]:
  rows = []
  offset = 0
  for line in text.splitlines(keepends=True):
    content = line.rstrip('\r\n')
    match = _BULLET.match(content)
    if match:
      body_start = match.end('prefix')
      body_end = len(content.rstrip(' \t'))
      body = content[body_start:body_end]
      done = len(body) >= 4 and body.startswith('~~') and body.endswith('~~')
      if done:
        idea_start, idea_end = body_start + 2, body_end - 2
        expected = content[idea_start:idea_end]
      else:
        idea_start, idea_end = body_start, body_end
        expected = body
      if expected.strip():
        prefix = text[:offset + idea_start]
        through = text[:offset + idea_end]
        rows.append({
            'path': path,
            'revision': revision,
            'start': _utf16_length(prefix),
            'end': _utf16_length(through),
            'expected': expected,
            'done': done,
        })
    offset += len(line)
  return rows


def list_ideas(vault) -> list[dict]:
  """List direct ``Ideas/*.md`` bullets with canonical source spans."""
  paths = vault.ls('Ideas')
  if paths is None:
    return []
  ideas = []
  for path in paths:
    if '/' in path.removeprefix('Ideas/') or not path.casefold().endswith('.md'):
      continue
    text, revision = vault.read(path)
    ideas.extend(_idea_rows(path, text, revision))
  return ideas


def strike_idea(vault, path: str, revision: str, start: int, end: int,
                expected: str) -> dict:
  """Wrap the exact revision-bound idea span in Markdown strike markers."""
  children = vault.ls('Ideas')
  if children is None or path not in children or not path.casefold().endswith('.md'):
    raise InvalidPath(f'Not an Ideas note: {path}')

  text, current_revision = vault.read(path)
  if current_revision != revision:
    raise RevisionConflict(text, current_revision)
  if not any(row['path'] == path and row['revision'] == revision
             and row['start'] == start and row['end'] == end
             and row['expected'] == expected and not row['done']
             for row in _idea_rows(path, text, current_revision)):
    raise IdeaSpanMismatch('The selected span is not an unfinished Ideas bullet.')
  if not isinstance(expected, str):
    raise IdeaSpanMismatch('Expected idea text must be a string.')
  try:
    start_index = _codepoint_offset(text, start)
    end_index = _codepoint_offset(text, end)
  except IdeaSpanMismatch:
    raise
  if end_index < start_index or text[start_index:end_index] != expected:
    raise IdeaSpanMismatch('The selected text no longer matches this idea.')

  updated = text[:start_index] + '~~' + expected + '~~' + text[end_index:]
  return vault.write(path, updated, revision)
