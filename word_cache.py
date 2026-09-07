import logging
import os
import threading

from collections import OrderedDict

from file_manager import FileManager, ROOT_DIR

logger = logging.getLogger(__name__)

# Roughly 110 MB at the 57 bytes a word this corpus averages, which holds
# most of a working session.
DEFAULT_MAX_WORDS = 2_000_000


class CachingFileManager(FileManager):
  """A FileManager that remembers the words it has already read.

  The terminal does not need this, because a person types slower than a
  parse. A server does: clicking through a library turns every folder into a
  parse, and the largest dictionary takes a quarter of a second.

  Entries are keyed by path and modification time, so editing a text
  reparses it. The cache is bounded by total words rather than by number of
  files, because pools here vary by two orders of magnitude.
  """

  def __init__(self, root = ROOT_DIR, max_words = DEFAULT_MAX_WORDS):
    super().__init__(root)
    self.max_words = max_words
    self._lock = threading.Lock()
    self._entries = OrderedDict()   # library path -> (mtime, words)
    self._words = 0
    self.hits = 0
    self.misses = 0


  # The words in a file, from memory when we have them.
  #
  # The returned list is shared with the cache and must not be mutated.
  def get_words(self, path: str) -> list[str]:
    stamp = self._mtime(path)

    if stamp is not None:
      with self._lock:
        entry = self._entries.get(path)
        if entry is not None and entry[0] == stamp:
          self._entries.move_to_end(path)
          self.hits += 1
          return entry[1]

    # Parsed outside the lock on purpose. A parse held under it would queue
    # every other request behind one click on a book.
    words = super().get_words(path)
    self.misses += 1
    if stamp is not None:
      self._store(path, stamp, words)
    return words


  # The size of a file we have already read, or None. Never parses, which is
  # what makes it safe to call while listing a folder.
  def cached_size(self, path: str) -> int | None:
    with self._lock:
      entry = self._entries.get(path)
      return len(entry[1]) if entry is not None else None


  def stats(self) -> dict:
    with self._lock:
      return {'files': len(self._entries), 'words': self._words,
              'hits': self.hits, 'misses': self.misses}


  # Reads files now, ignoring the ones that fail. Warming is best effort:
  # a text that cannot be read is a problem for whoever asks for it, not for
  # startup.
  def warm(self, paths) -> int:
    done = 0
    for path in paths:
      try:
        self.get_words(path)
        done += 1
      except Exception:
        logger.debug('could not warm %s', path, exc_info=True)
    return done


  def warm_in_background(self, paths) -> threading.Thread:
    thread = threading.Thread(target=self.warm, args=(list(paths),),
                              name='warm', daemon=True)
    thread.start()
    return thread


  def _mtime(self, path):
    try:
      return os.path.getmtime(self.resolve(path))
    except OSError:
      # Missing or unreadable: fall through so get_words raises the real
      # error with the real message.
      return None


  def _store(self, path, stamp, words):
    with self._lock:
      previous = self._entries.pop(path, None)
      if previous is not None:
        self._words -= len(previous[1])

      self._entries[path] = (stamp, words)
      self._words += len(words)

      # Evict oldest first, but never the entry just stored: a single pool
      # larger than the whole budget should still be usable.
      while self._words > self.max_words and len(self._entries) > 1:
        _, (_, evicted) = self._entries.popitem(last=False)
        self._words -= len(evicted)
