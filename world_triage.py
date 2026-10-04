"""Per-world dismissals ("not a problem") for the housekeeping and lexicon views.

Dismissals are user state, not vault content and not derived data, so they
live outside the vault: ``<base>/<world id>/triage.json`` where the world id
is the first sixteen hex digits of the SHA-256 of the vault root's real path.
The base directory is injectable so tests, and later a hosted world's private
root, can choose where it is.

Keys, by kind:

* ``name``    a name-without-entry phrase, NFC + casefolded
* ``drift``   ``from→to`` for a spelling-drift pair
* ``word``    a lexicon word that is a real word, NFC + casefolded
* ``mention`` ``source_path|target_path`` for an unlinked mention
* ``target``  a target path: never suggest linking it (every unlinked
  mention of it is hidden, and Nearby stops offering it as a named mention)
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import tempfile
import threading
import unicodedata

KINDS = ("name", "drift", "word", "mention", "target")
MAX_KEY_LENGTH = 1000
DRIFT_ARROW = "→"
_FILE_NAME = "triage.json"
_VERSION = 1


def default_base_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".randomwords", "worlds")


def world_id(vault_root: str) -> str:
    real = os.path.realpath(vault_root)
    return hashlib.sha256(real.encode("utf-8")).hexdigest()[:16]


def normalize_key(kind: str, key: str) -> str:
    """Canonical spelling of a key, so the UI may send text as displayed."""
    if kind in ("name", "word"):
        return unicodedata.normalize("NFC", key).casefold()
    return key


def drift_key(source: str, target: str) -> str:
    return f"{source}{DRIFT_ARROW}{target}"


def mention_key(source_path: str, target_path: str) -> str:
    return f"{source_path}|{target_path}"


def validate(kind, key) -> str | None:
    """An error message for an invalid kind or key, else None."""
    if kind not in KINDS:
        return "Kind must be one of: " + ", ".join(KINDS) + "."
    if not isinstance(key, str) or not key.strip():
        return "Key must be nonempty text."
    if len(key) > MAX_KEY_LENGTH:
        return f"Key must be at most {MAX_KEY_LENGTH} characters."
    return None


_locks_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}


def _lock_for(path: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(path, threading.RLock())


class TriageStore:
    """A small JSON file of dismissals with atomic, locked read-modify-write."""

    def __init__(self, directory: str):
        self.directory = directory
        self.path = os.path.join(directory, _FILE_NAME)

    # -- reading ---------------------------------------------------------

    def _load(self) -> dict[tuple[str, str], str]:
        """Dismissals as ``{(kind, key): dismissed_at}``; empty if unusable."""
        try:
            with open(self.path, "rb") as source:
                raw = source.read()
        except FileNotFoundError:
            return {}
        except OSError:
            return {}
        try:
            document = json.loads(raw.decode("utf-8"))
            rows = document["dismissed"]
            if document.get("version") != _VERSION or not isinstance(rows, list):
                raise ValueError("unexpected shape")
            found = {}
            for row in rows:
                kind, key, stamp = row["kind"], row["key"], row.get("at", "")
                if kind not in KINDS or not isinstance(key, str) or not key:
                    raise ValueError("bad row")
                found[(kind, key)] = stamp if isinstance(stamp, str) else ""
            return found
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            self._keep_corrupt_copy(raw)
            return {}

    def _keep_corrupt_copy(self, raw: bytes) -> None:
        """Preserve an unreadable file before a later write replaces it."""
        try:
            candidate, number = self.path + ".corrupt", 0
            while os.path.exists(candidate):
                with open(candidate, "rb") as existing:
                    if existing.read() == raw:
                        return
                number += 1
                candidate = f"{self.path}.corrupt.{number}"
            os.makedirs(self.directory, mode=0o700, exist_ok=True)
            with open(candidate, "wb") as copy:
                copy.write(raw)
        except OSError:
            pass

    def dismissed(self) -> list[dict]:
        with _lock_for(self.path):
            found = self._load()
        return [{"kind": kind, "key": key, "at": stamp}
                for (kind, key), stamp in sorted(found.items())]

    def keys(self, kind: str) -> frozenset[str]:
        with _lock_for(self.path):
            return frozenset(key for (k, key) in self._load() if k == kind)

    # -- writing ---------------------------------------------------------

    def _write(self, found: dict[tuple[str, str], str]) -> None:
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        document = {"version": _VERSION,
                    "dismissed": [{"kind": kind, "key": key, "at": stamp}
                                  for (kind, key), stamp in sorted(found.items())]}
        handle, temporary = tempfile.mkstemp(dir=self.directory, prefix=".triage-",
                                             suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                json.dump(document, output, ensure_ascii=False, indent=1)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        try:
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass

    def dismiss(self, kind: str, key: str) -> bool:
        """Record a dismissal; False when it was already recorded."""
        key = normalize_key(kind, key)
        with _lock_for(self.path):
            found = self._load()
            if (kind, key) in found:
                return False
            found[(kind, key)] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._write(found)
            return True

    def restore(self, kind: str, key: str) -> bool:
        """Remove a dismissal; False when there was none."""
        key = normalize_key(kind, key)
        with _lock_for(self.path):
            found = self._load()
            if (kind, key) not in found:
                return False
            del found[(kind, key)]
            self._write(found)
            return True


# ---------------------------------------------------------------------------
# Locating the store for a request

_base_dir: str | None = None
_stores: dict[tuple[str, str], TriageStore] = {}


def set_base_dir(path: str | None) -> None:
    """Choose where worlds keep private state; None restores the default.

    Tests use a temporary directory here, and a hosted deployment maps it to
    the world's private root.
    """
    global _base_dir
    with _locks_guard:
        _base_dir = path
        _stores.clear()


def store_for(vault_root: str) -> TriageStore:
    """The (cached) store for the world whose vault is at ``vault_root``."""
    with _locks_guard:
        base = _base_dir or default_base_dir()
        real = os.path.realpath(vault_root)
        cache_key = (base, real)
        store = _stores.get(cache_key)
        if store is None:
            store = _stores[cache_key] = TriageStore(
                os.path.join(base, world_id(real)))
        return store


def store_for_request(req) -> TriageStore | None:
    vault = getattr(req, "vault", None)
    root = getattr(vault, "root", None)
    return store_for(root) if isinstance(root, str) else None


# ---------------------------------------------------------------------------
# Filtering helpers shared by the health and lexicon routes

def split_dismissed(rows, kind_keys: frozenset[str], key_of, *, extra=None):
    """Return ``(kept, dismissed_count)``.

    ``key_of(row)`` gives a row's key for this kind; ``extra(row)`` may
    dismiss a row for another reason (for instance a dismissed word).
    """
    kept = []
    for row in rows:
        if key_of(row) in kind_keys or (extra is not None and extra(row)):
            continue
        kept.append(row)
    return kept, len(rows) - len(kept)


def name_key(row: dict) -> str:
    return normalize_key("name", row["phrase"])


def mention_row_key(row: dict) -> str:
    return mention_key(row["source_path"], row["target_path"])


def drift_row_key(row: dict) -> str:
    source = row["from"]
    target = row["to"]
    return drift_key(source, target)
