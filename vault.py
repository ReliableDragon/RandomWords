"""Safe, revision-aware access to a Markdown vault."""

import hashlib
import os
import tempfile
import threading
import unicodedata


class InvalidPath(Exception):
  """A path that is not a permitted vault path."""


class UnreadableSource(Exception):
  """A vault source could not be read or written."""


class RevisionConflict(Exception):
  """The source changed since the caller last read it."""

  def __init__(self, current_text: str, current_revision: str):
    super().__init__('The note changed since it was read.')
    self.current_text = current_text
    self.current_revision = current_revision


class DestinationConflict(Exception):
  """A create destination already exists or has an equivalent spelling."""

  def __init__(self, path: str, existing_path: str | None = None):
    self.path = path
    self.existing_path = existing_path or path
    super().__init__(f'A note already uses this destination: {self.existing_path}')


def _revision(data: bytes) -> str:
  return 'sha256:' + hashlib.sha256(data).hexdigest()


def _key(path: str) -> str:
  return unicodedata.normalize('NFC', path).casefold()


class VaultManager:
  """Access Markdown notes below one root, with atomic revision checks."""

  def __init__(self, root: str, recovery_dir: str | None = None):
    self.root = os.path.realpath(root)
    if recovery_dir is None:
      recovery_dir = os.path.join(os.path.expanduser('~'), '.randomwords', 'recovery')
    self.recovery_dir = os.path.realpath(recovery_dir)
    if self.recovery_dir == self.root or self.recovery_dir.startswith(self.root + os.sep):
      raise ValueError('Recovery directory must be outside the vault.')
    self._locks_guard = threading.Lock()
    self._locks: dict[str, threading.RLock] = {}

  def _lock(self, path: str) -> threading.RLock:
    with self._locks_guard:
      return self._locks.setdefault(path, threading.RLock())

  def resolve(self, path: str) -> str:
    if (not isinstance(path, str) or path.startswith('/') or '\\' in path
        or '\x00' in path):
      raise InvalidPath(f'Not a path in the vault: {path}')
    parts = path.split('/')
    if path == '':
      parts = []
    if any(p in ('', '.', '..') or p.startswith('.') for p in parts):
      raise InvalidPath(f'Not a path in the vault: {path}')
    full = os.path.realpath(os.path.join(self.root, *parts))
    if full != self.root and not full.startswith(self.root + os.sep):
      raise InvalidPath(f'Not a path in the vault: {path}')
    return full

  def _note_path(self, path: str) -> str:
    full = self.resolve(path)
    if not path.casefold().endswith('.md'):
      raise InvalidPath(f'Only Markdown notes are allowed: {path}')
    return full

  def relative(self, full: str) -> str:
    rel = os.path.relpath(os.path.realpath(full), self.root)
    return '' if rel == '.' else rel.replace(os.sep, '/')

  def ls(self, path: str = '') -> list[str] | None:
    folder = self.resolve(path)
    try:
      entries = os.listdir(folder)
    except (OSError, NotADirectoryError):
      return None
    out = []
    for name in entries:
      if name.startswith('.'):
        continue
      candidate = name if not path else path + '/' + name
      try:
        full = self.resolve(candidate)
      except InvalidPath:
        continue
      if os.path.isdir(full) or (name.casefold().endswith('.md') and os.path.isfile(full)):
        out.append(self.relative(full))
    return sorted(out)

  def _read_bytes(self, path: str) -> bytes:
    full = self._note_path(path)
    try:
      with open(full, 'rb') as f:
        return f.read()
    except (OSError, IsADirectoryError) as e:
      raise UnreadableSource(f'Could not read {path}: {e}') from None

  def read(self, path: str) -> tuple[str, str]:
    data = self._read_bytes(path)
    try:
      return data.decode('utf-8'), _revision(data)
    except UnicodeDecodeError:
      raise UnreadableSource(f'Invalid UTF-8 in {path}') from None

  def _write_atomic(self, path: str, data: bytes, exclusive: bool = False) -> None:
    full = self._note_path(path)
    parent = os.path.dirname(full)
    tmp = None
    try:
      os.makedirs(parent, exist_ok=True)
      fd, tmp = tempfile.mkstemp(prefix='.randomwords-', suffix='.tmp', dir=parent)
      with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
      if exclusive:
        # A hard link gives us an atomic no-clobber install on the same
        # filesystem; the temporary file is removed in the finally block.
        os.link(tmp, full)
        os.unlink(tmp)
        tmp = None
      else:
        os.replace(tmp, full)
      tmp = None
    except OSError as e:
      if exclusive and isinstance(e, FileExistsError):
        raise DestinationConflict(path) from None
      raise UnreadableSource(f'Could not write {path}: {e}') from None
    finally:
      if tmp and os.path.exists(tmp):
        os.unlink(tmp)

  def write(self, path: str, text: str, revision: str,
            replace_revision: str | None = None) -> dict:
    with self._lock(path):
      current = self._read_bytes(path)
      current_revision = _revision(current)
      if current_revision != revision:
        if replace_revision != current_revision:
          try:
            current_text = current.decode('utf-8')
          except UnicodeDecodeError:
            current_text = current.decode('utf-8', errors='replace')
          raise RevisionConflict(current_text, current_revision)
        recovery = self._save_recovery(path, current, current_revision)
      else:
        recovery = None
      data = self._preserve_conventions(current, text)
      self._write_atomic(path, data)
      result = {'path': path, 'revision': _revision(data)}
      if recovery:
        result['recovery_path'] = recovery
      return result

  def _save_recovery(self, path: str, data: bytes, revision: str) -> str:
    canonical_path = unicodedata.normalize('NFC', path).casefold()
    path_hash = hashlib.sha256(canonical_path.encode('utf-8')).hexdigest()[:16]
    safe = path.replace('/', '__')
    os.makedirs(self.recovery_dir, exist_ok=True)
    destination = os.path.join(self.recovery_dir, f'{safe}.{path_hash}.{revision[7:]}.md')
    try:
      with open(destination, 'xb') as f:
        f.write(data)
    except FileExistsError:
      pass
    except OSError as e:
      raise UnreadableSource(f'Could not save recovery copy: {e}') from None
    return destination

  @staticmethod
  def _preserve_conventions(original: bytes, text: str) -> bytes:
    """Encode edited text using the note's BOM, newline and EOF conventions."""
    bom = original.startswith(b'\xef\xbb\xbf')
    source = original[3:] if bom else original
    try:
      original_text = source.decode('utf-8')
    except UnicodeDecodeError:
      original_text = ''
    incoming = text[1:] if text.startswith('\ufeff') else text
    logical_original = original_text.replace('\r\n', '\n').replace('\r', '\n')
    logical_incoming = incoming.replace('\r\n', '\n').replace('\r', '\n')
    if logical_incoming == logical_original:
      return original
    newline = '\r\n' if '\r\n' in original_text else '\n'
    final_newline = original_text.endswith(('\n', '\r'))
    normalized = logical_incoming
    if final_newline:
      if not normalized.endswith('\n'):
        normalized += '\n'
    else:
      normalized = normalized.rstrip('\n')
    encoded = normalized.replace('\n', newline).encode('utf-8')
    return (b'\xef\xbb\xbf' if bom else b'') + encoded

  def create(self, path: str, text: str) -> dict:
    self._note_path(path)
    key = _key(path)
    with self._locks_guard:
      lock = self._locks.setdefault('create:' + key, threading.RLock())
    with lock:
      for existing in self._all_note_paths():
        if _key(existing) == key:
          raise DestinationConflict(path, existing)
      data = text.encode('utf-8')
      self._write_atomic(path, data, exclusive=True)
      return {'path': path, 'revision': _revision(data)}

  def _all_note_paths(self) -> list[str]:
    found = []
    for base, dirs, files in os.walk(self.root, followlinks=False):
      dirs[:] = [d for d in dirs if not d.startswith('.')]
      for filename in files:
        if filename.startswith('.') or not filename.casefold().endswith('.md'):
          continue
        full = os.path.join(base, filename)
        try:
          self.resolve(self.relative(full))
        except InvalidPath:
          continue
        found.append(self.relative(full))
    return found

  def stat_all(self) -> dict[str, tuple[int, int]]:
    out = {}
    for path in self._all_note_paths():
      try:
        st = os.stat(self.resolve(path))
        out[path] = (st.st_mtime_ns, st.st_size)
      except OSError:
        continue
    return out
