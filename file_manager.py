import os
import pathlib
import re
import logging
import random
import tempfile

logger = logging.getLogger(__name__)

# The sources directory is located relative to this file rather than to the
# current working directory, so the program can be started from anywhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(_HERE, 'sources')

# A word is a run of letters/digits, optionally joined by internal
# apostrophes or hyphens ("well-known", "ain't"). '[^\W_]' is Unicode-aware,
# so accented letters are matched without a hand-written character range,
# and every other character -- including em and en dashes -- separates words.
WORD_RE = re.compile(r"[^\W_]+(?:['’‐-][^\W_]+)*")

GUTENBERG_HEADER = '*** START OF THE PROJECT GUTENBERG EBOOK'
GUTENBERG_FOOTER = '*** END OF THE PROJECT GUTENBERG EBOOK'

# The one folder under the library root this class will ever write to.
CUSTOM_DIR = 'custom'

# The shape a pool name must have to become a filename: the same `\w+`
# alias_load_cmd.py already enforces for an alias, duplicated here rather
# than imported so that this module, which every command depends on, does
# not have to depend back on a command module.
POOL_FILE_NAME = re.compile(r'\w+\Z')


# The umask cannot be read without being set, so it is set and put straight
# back. Only file creation in this process can see the gap.
def _umask() -> int:
  value = os.umask(0)
  os.umask(value)
  return value


class InvalidPath(Exception):
  """A path that does not name something inside the library.

  The message is user-facing."""


class UnreadableSource(Exception):
  """A text that could not be read. The message is user-facing."""


class FileManager():

  # Every path in and out of this class is relative to `root`, and `root` is
  # set once. There is no working directory, so there is no per-session
  # filesystem state for concurrent callers to race over, and no path that
  # means somewhere else.
  #
  # root: the one directory this manager can see.
  def __init__(self, root = ROOT_DIR):
    self.root = os.path.realpath(root or '.')

  ###
  ### PATH METHODS
  ###

  # Turns a library path into an absolute one.
  #
  # There is deliberately no branch that returns a path outside the root. An
  # absolute path, a '..' segment, or a symlink pointing out of the tree is
  # refused rather than resolved, which is why callers can pass user input
  # here without sanitising it first.
  def resolve(self, path: str) -> str:
    if path.startswith('/'):
      raise InvalidPath(f'Not a path in the library: {path}')

    parts = [p for p in path.split('/') if p not in ('', '.')]
    if '..' in parts:
      raise InvalidPath(f'Not a path in the library: {path}')

    full = os.path.realpath(os.path.join(self.root, *parts))
    # A symlink is not a string, so the string checks above are not enough.
    if full != self.root and not full.startswith(self.root + os.sep):
      raise InvalidPath(f'Not a path in the library: {path}')
    return full


  # The library path for an absolute one. '' names the root itself.
  def relative(self, full: str) -> str:
    rel = os.path.relpath(os.path.realpath(full), self.root)
    return '' if rel == '.' else rel


  def is_dir(self, path: str) -> bool:
    try:
      return os.path.isdir(self.resolve(path))
    except InvalidPath:
      return False

  ###
  ### LIST METHODS
  ###

  # Strips Project Gutenberg licence text, keeping only what lies between
  # each START/END marker pair. Text without a header is returned unchanged.
  def remove_gutenberg(self, txt):
    if GUTENBERG_HEADER not in txt:
      return txt

    index = 0
    out_txt = ''
    while GUTENBERG_HEADER in txt[index:]:
      header_start = txt.index(GUTENBERG_HEADER, index)
      header_end = txt.index('***', header_start + 1)
      try:
        footer_start = txt.index(GUTENBERG_FOOTER, header_end)
      except ValueError:
        # Header with no matching footer: keep the rest of the file.
        out_txt += txt[header_end + 3:]
        break
      out_txt += txt[header_end + 3:footer_start]
      index = footer_start + 1
    return out_txt


  # Gets all of the words present in a file.
  #
  # path: A library path to the file to read.
  # Returns: The distinct lower-cased words in the file.
  # Raises: InvalidPath, or UnreadableSource if the file cannot be read.
  def get_words(self, path: str) -> list[str]:
    full = self.resolve(path)

    try:
      with open(full, encoding='utf-8', errors='replace') as f:
        txt = f.read()
    except OSError:
      # `from None`: this replaces the OSError rather than being an accident
      # while handling it, so a stray traceback shows one exception, not two.
      raise UnreadableSource(f'Invalid filename: {path}') from None

    txt = self.remove_gutenberg(txt)
    tokens = WORD_RE.findall(txt)
    # Lower-case before de-duplicating, so a word that appears both
    # capitalised and not is not twice as likely to be chosen.
    return sorted({t.lower() for t in tokens if any(c.isalpha() for c in t)})


  # Lists a folder, or the library root when no path is given.
  #
  # Returns: Library paths for the non-hidden folders and .txt files found,
  # or None if the folder could not be read.
  def ls(self, path: str = '') -> list[str] | None:
    try:
      entries = list(pathlib.Path(self.resolve(path)).iterdir())
    except (FileNotFoundError, NotADirectoryError, PermissionError):
      return None
    keep = [f for f in entries
            if (f.is_dir() and not f.name.startswith('.')) or f.suffix == '.txt']
    return sorted(self.relative(str(f)) for f in keep)


  # Every .txt file at or below a folder, as library paths.
  def get_txts(self, path: str = '') -> list[str]:
    base = self.resolve(path)
    return sorted(self.relative(str(p)) for p in pathlib.Path(base).rglob('*.txt'))

  ###
  ### RAND FUNCTIONS
  ###

  # A random .txt file, picking evenly between every file below the folder.
  # Returns None if there are none.
  def rand_file(self, path: str = '') -> str | None:
    txts = self.get_txts(path)
    if not txts:
      return None
    return random.choice(txts)


  # A random file found by choosing evenly among the entries of the folder,
  # then of the chosen subfolder, and so on. Returns None if none was found.
  def rand_dir(self, path: str = '') -> str | None:
    options = self.ls(path)
    if not options:
      return None

    options = list(options)
    while options:
      choice = random.choice(options)
      if not self.is_dir(choice):
        return choice
      # A folder that turns out to hold no .txt files anywhere is skipped
      # rather than returning nothing.
      result = self.rand_dir(choice)
      if result is not None:
        return result
      options.remove(choice)
    return None

  ###
  ### WRITE METHODS
  ###
  #
  # Everything above resolves a path a user typed, which is why `resolve`
  # has to defend against `..`, a leading `/`, and a symlink leading out of
  # the tree. Nothing below takes a path at all: `save_cmd.py` is the only
  # caller, and the only thing it ever hands these methods is a bare pool
  # name, the same shape alias_load_cmd.py already requires for an alias.
  # There is no user-facing argument here that could carry a `/` or a `..`
  # to begin with, so there is no traversal to defend against; the checks
  # below exist to keep that invariant rather than to resolve one.

  # Turns a bare pool name into the absolute path of its file under
  # `sources/custom/`.
  #
  # Raises: InvalidPath if `name` is not a bare `\w+` name.
  def write_path(self, name: str) -> str:
    if not POOL_FILE_NAME.match(name):
      raise InvalidPath(
          f'"{name}" cannot be a pool name. Use letters, digits and underscores.')
    return os.path.join(self.root, CUSTOM_DIR, f'{name}.txt')


  # Whether a pool has already been written to disk under this name, so a
  # caller can ask before overwriting it.
  #
  # Raises: InvalidPath if `name` is not a bare `\w+` name.
  def pool_exists(self, name: str) -> bool:
    return os.path.exists(self.write_path(name))


  # Writes `words` to the custom pool file for `name`, one per line, UTF-8,
  # with a trailing newline. Returns the library path they were written to.
  #
  # The write lands in a temporary file in the same folder first, then
  # `os.replace` swaps it into place. That swap is atomic on every platform
  # this runs on, so a process killed mid-write leaves either the old file
  # or the new one, never a half-written pool that `load` would happily
  # read as truncated.
  #
  # Raises: InvalidPath if `name` is not a bare `\w+` name, or
  # UnreadableSource if the write itself fails.
  def write_pool(self, name: str, words: list[str]) -> str:
    full = self.write_path(name)
    folder = os.path.dirname(full)
    tmp_path = None
    try:
      os.makedirs(folder, exist_ok=True)
      fd, tmp_path = tempfile.mkstemp(dir=folder, prefix=f'.{name}.', suffix='.tmp')
      with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.writelines(word + '\n' for word in words)
      # mkstemp creates a private file, which would leave a saved pool less
      # readable than every text beside it in the library. Widened to the
      # ordinary mode for a file, less whatever the umask takes off.
      os.chmod(tmp_path, 0o666 & ~_umask())
      os.replace(tmp_path, full)
    except OSError as e:
      if tmp_path is not None and os.path.exists(tmp_path):
        os.remove(tmp_path)
      raise UnreadableSource(f'Could not write {name}: {e}') from None
    return self.relative(full)
