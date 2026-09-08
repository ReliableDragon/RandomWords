import array
import bisect
import json
import logging
import os
import random
import sys
import threading

from file_manager import FileManager, UnreadableSource

logger = logging.getLogger(__name__)

# The built index lives beside the library it describes, one directory up
# from the library root, because it is derived data and the library is input.
# It is gitignored.
#
# Beside the *library* and not beside the program, which is what this was at
# first and was wrong: an index belongs to the texts it was built from. A
# test pointing a file manager at a temporary tree would otherwise read and
# overwrite the real index, and a second library would silently share the
# first one's answers.
CACHE_FILE = 'library.index'

# Bumped whenever the on-disk layout changes, so an old file is rebuilt
# rather than misread.
FORMAT_VERSION = 1

# Text ids are stored as unsigned shorts, which is four hundred times the
# current library and still only two bytes a posting.
MAX_TEXTS = 65535

# Above this, a word is in so many texts that its nearest neighbours are
# whatever else is common, which is not worth the scan it costs to find out.
NEIGHBOUR_LIMIT = 25

# Folders that hold word lists rather than books, and so are not evidence
# about a word.
#
# Counting them wrecks the thing the index is for. `harpooneer` appears in
# Moby Dick and in the 450k dictionary, and a dictionary is not a second
# usage: with the lists counted it looks like a word two texts share, and
# `rare 1` drops it. Without them Moby Dick's unique vocabulary goes from
# 1,481 words to 2,240, and `harpooneer` is in it. `custom/` is excluded for
# a second reason as well: it is where saved pools are written, and a pool
# saved from a book would otherwise make that book's words look shared.
NOT_BOOKS = ('dicts/', 'custom/')


def cache_dir_for(file_manager) -> str:
  return os.path.join(os.path.dirname(file_manager.root), '.cache')


class WordIndex():
  """Which texts each word appears in.

  Everything else here is per-file: a pool is one text, or a set operation
  over two of them. This is the one structure that knows the library as a
  whole, and it is what lets a word be judged rare rather than merely absent
  from a frequency list.

  The shape is the classic flat inverted index: the vocabulary sorted once,
  an offset per word into a single postings array, and the postings end to
  end. A dictionary of sets was the obvious first try and cost 255 MB; this
  costs about 12 MB beyond the strings, which the word cache is holding
  anyway, and a lookup is a binary search rather than a hash of a long word.
  """

  def __init__(self, file_manager: FileManager, cache_dir: str = None):
    self.fm = file_manager
    self._cache_dir = cache_dir
    # Guards every field below. Held only around reads and the final swap,
    # never around a parse: building takes seconds and must not block a draw.
    self._lock = threading.RLock()
    # Separate from the lock above, and held for the whole of a build, so
    # that a second caller waits for the first one's index instead of
    # finding the build already in progress and giving up.
    self._build_lock = threading.Lock()
    self._texts = []                  # text id -> library path
    self._vocab = []                  # distinct words, sorted
    self._offsets = array.array('I')  # word i occupies postings[o[i]:o[i+1]]
    self._postings = array.array('H')
    self._built_from = {}             # library path -> mtime when indexed
    self.ready = False
    self.building = False


  # Worked out on demand rather than in __init__, because only save and load
  # need it: building an index should not require a file manager with a real
  # directory behind it.
  @property
  def cache_dir(self) -> str:
    if self._cache_dir is None:
      self._cache_dir = cache_dir_for(self.fm)
    return self._cache_dir


  ###
  ### BUILDING
  ###

  # Reads every text and indexes it. Returns the number of texts indexed.
  #
  # The parse happens outside the lock, against a fresh set of arrays that
  # replace the live ones in one assignment at the end. A command running
  # while this happens sees the old index or the new one, never half of each.
  def build(self, paths: list[str] | None = None) -> int:
    with self._lock:
      if self.building:
        return 0
      self.building = True

    try:
      paths = sorted(self.books() if paths is None else paths)
      if len(paths) > MAX_TEXTS:
        raise ValueError(f'The index holds at most {MAX_TEXTS} texts.')

      postings = {}
      texts = []
      stamps = {}
      for path in paths:
        try:
          words = self.fm.get_words(path)
        except (UnreadableSource, OSError):
          # A text that cannot be read is missing from the index, which
          # makes its words look rarer than they are. That is a better
          # failure than refusing to build at all.
          logger.debug('could not index %s', path, exc_info=True)
          continue
        text_id = len(texts)
        texts.append(path)
        stamps[path] = self._mtime(path)
        for word in words:
          postings.setdefault(word, []).append(text_id)

      vocab = sorted(postings)
      flat = array.array('H')
      offsets = array.array('I')
      offsets.append(0)
      for word in vocab:
        flat.extend(postings[word])
        offsets.append(len(flat))

      with self._lock:
        self._texts = texts
        self._vocab = vocab
        self._offsets = offsets
        self._postings = flat
        self._built_from = stamps
        self.ready = True
      return len(texts)
    finally:
      with self._lock:
        self.building = False


  # The texts the index is built from: everything in the library that is a
  # book rather than a word list.
  def books(self) -> list[str]:
    return [p for p in self.fm.get_txts() if not p.startswith(NOT_BOOKS)]


  def build_in_background(self, paths=None) -> threading.Thread:
    thread = threading.Thread(target=self.build, args=(paths,),
                              name='index', daemon=True)
    thread.start()
    return thread


  # Loads a saved index if it still matches the library, and builds one
  # otherwise. Returns True if the saved index was usable.
  def load_or_build(self) -> bool:
    if self.load():
      return True
    self.build()
    self.save()
    return False


  # Makes the index usable, paying for it here if nobody has yet.
  #
  # Nothing builds this at startup on purpose. The terminal opens instantly
  # today and should keep doing so; a person who never asks about the
  # library as a whole should never wait for it to be read. The first `rare`
  # or `which` of the first run takes about seven seconds, and every run
  # after that loads the saved index in twenty milliseconds.
  #
  # The separate lock is what keeps two callers from both building: the
  # flag inside build() makes the second one return without an index.
  def ensure_ready(self) -> bool:
    with self._build_lock:
      if not self.ready:
        self.load_or_build()
      return self.ready


  ###
  ### QUERIES
  ###

  # The library paths of the texts containing a word, in library order.
  def texts_for(self, word: str) -> list[str]:
    with self._lock:
      start, end = self._span(word.lower())
      return [self._texts[i] for i in self._postings[start:end]]


  # How many texts contain a word. Zero for a word the library never uses.
  def doc_count(self, word: str) -> int:
    with self._lock:
      start, end = self._span(word.lower())
      return end - start


  # The words of `words` that appear in at most `max_texts` texts.
  #
  # This is a filter over a pool rather than a query over the library, so it
  # composes with everything else: the pool it narrows can be a book, a saved
  # pool, or the result of a set operation.
  def filter_rare(self, words, max_texts: int = 1) -> list[str]:
    with self._lock:
      kept = []
      for word in words:
        start, end = self._span(word.lower())
        count = end - start
        # A word the index has never seen is not evidence of rarity, it is
        # evidence that the pool came from outside the library.
        if 0 < count <= max_texts:
          kept.append(word)
      return kept


  # The words whose set of texts most resembles this word's, by Jaccard
  # similarity, best first.
  #
  # Candidates are only the words sharing at least one text, gathered from
  # the texts themselves, so the scan is proportional to what the word could
  # plausibly resemble rather than to the size of the library.
  def neighbours(self, word: str, limit: int = 10) -> list[tuple[str, float]]:
    word = word.lower()
    with self._lock:
      start, end = self._span(word)
      if start == end:
        return []
      mine = set(self._postings[start:end])
      paths = [self._texts[i] for i in mine]

    seen = set()
    for path in paths:
      try:
        seen.update(self.fm.get_words(path))
      except (UnreadableSource, OSError):
        continue
    seen.discard(word)

    scored = []
    with self._lock:
      for candidate in seen:
        c_start, c_end = self._span(candidate)
        if c_start == c_end:
          continue
        theirs = set(self._postings[c_start:c_end])
        shared = len(mine & theirs)
        if not shared:
          continue
        scored.append((candidate, shared / len(mine | theirs)))

    # Ties are broken at random, and the shuffle-then-stable-sort is how.
    #
    # An alphabetical tiebreak looked tidier and was useless: a word in two
    # texts ties at 1.0 with every other word those two texts share, so
    # `like harpooneer` answered "a-plenty, abandonedly, aboundingly" --
    # the front of an alphabet, not the front of a ranking. Drawing from
    # the tier is also what the rest of this tool does with a set of
    # equally good words.
    random.shuffle(scored)
    scored.sort(key=lambda pair: -pair[1])
    return scored[:limit]


  # True when a word is in so many texts that neighbours would be noise.
  def too_common(self, word: str) -> bool:
    return self.doc_count(word) > NEIGHBOUR_LIMIT


  def stats(self) -> dict:
    with self._lock:
      return {'ready': self.ready, 'building': self.building,
              'texts': len(self._texts), 'words': len(self._vocab),
              'postings': len(self._postings)}


  ###
  ### PERSISTENCE
  ###

  # Writes the index beside the program so the next run does not pay for it.
  #
  # Written to a temporary name and moved into place, because a half-written
  # index that still passes its header check would be read as a real one.
  def save(self) -> bool:
    with self._lock:
      if not self.ready:
        return False
      header = {
        'version': FORMAT_VERSION,
        # Native byte order, because the arrays are written raw. A file
        # carried to a machine of the other endianness is rebuilt, not
        # silently misread.
        'byteorder': sys.byteorder,
        'texts': self._texts,
        'stamps': self._built_from,
        'vocab': len(self._vocab),
      }
      vocab = '\n'.join(self._vocab).encode('utf-8')
      offsets = self._offsets.tobytes()
      postings = self._postings.tobytes()

    head = json.dumps(header).encode('utf-8')
    path = os.path.join(self.cache_dir, CACHE_FILE)
    tmp = path + '.tmp'
    try:
      os.makedirs(self.cache_dir, exist_ok=True)
      with open(tmp, 'wb') as f:
        f.write(b'RWIDX\n')
        for blob in (head, vocab, offsets, postings):
          f.write(b'%d\n' % len(blob))
        for blob in (head, vocab, offsets, postings):
          f.write(blob)
      os.replace(tmp, path)
      return True
    except OSError:
      logger.debug('could not save the index', exc_info=True)
      try:
        os.remove(tmp)
      except OSError:
        pass
      return False


  # Reads a saved index, if there is one and the library still matches it.
  def load(self) -> bool:
    path = os.path.join(self.cache_dir, CACHE_FILE)
    try:
      with open(path, 'rb') as f:
        if f.readline() != b'RWIDX\n':
          return False
        sizes = [int(f.readline()) for _ in range(4)]
        head, vocab, offsets, postings = (f.read(n) for n in sizes)
    except (OSError, ValueError):
      return False

    try:
      header = json.loads(head)
    except ValueError:
      return False

    if header.get('version') != FORMAT_VERSION:
      return False
    if header.get('byteorder') != sys.byteorder:
      return False
    if not self._still_current(header.get('stamps') or {}):
      return False

    try:
      words = vocab.decode('utf-8').split('\n') if vocab else []
      o = array.array('I'); o.frombytes(offsets)
      p = array.array('H'); p.frombytes(postings)
    except (ValueError, UnicodeDecodeError):
      return False

    # A file that survived the header check can still be inconsistent, and
    # every query indexes into these arrays without checking.
    if len(o) != len(words) + 1 or (o and o[-1] != len(p)):
      return False

    with self._lock:
      self._texts = list(header.get('texts') or [])
      self._vocab = words
      self._offsets = o
      self._postings = p
      self._built_from = header.get('stamps') or {}
      self.ready = True
    return True


  ###
  ### INTERNALS
  ###

  # The slice of the postings array belonging to a word. Callers hold the
  # lock; this does no locking of its own so a loop can take it once.
  def _span(self, word: str) -> tuple[int, int]:
    i = bisect.bisect_left(self._vocab, word)
    if i == len(self._vocab) or self._vocab[i] != word:
      return (0, 0)
    return (self._offsets[i], self._offsets[i + 1])


  # True when the library is exactly the set of texts the index was built
  # from, each unmodified since. Anything else means a rebuild.
  def _still_current(self, stamps: dict) -> bool:
    try:
      current = self.books()
    except OSError:
      return False
    if set(current) != set(stamps):
      return False
    return all(self._mtime(path) == stamps[path] for path in current)


  def _mtime(self, path: str):
    try:
      return os.path.getmtime(self.fm.resolve(path))
    except OSError:
      return None
