import os
import pathlib
import re
import logging
import random

logger = logging.getLogger(__name__)

# The sources directory is located relative to this file rather than to the
# current working directory, so the program can be started from anywhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(_HERE, 'sources') + '/'

# A path typed with this prefix is interpreted as relative to the sources
# root instead of to the current directory.
SOURCES_PREFIX = 'sources/'

# A word is a run of letters/digits, optionally joined by internal
# apostrophes or hyphens ("well-known", "ain't"). '[^\W_]' is Unicode-aware,
# so accented letters are matched without a hand-written character range,
# and every other character -- including em and en dashes -- separates words.
WORD_RE = re.compile(r"[^\W_]+(?:['’‐-][^\W_]+)*")

GUTENBERG_HEADER = '*** START OF THE PROJECT GUTENBERG EBOOK'
GUTENBERG_FOOTER = '*** END OF THE PROJECT GUTENBERG EBOOK'


class UnreadableSource(Exception):
  """A text that could not be read. The message is user-facing."""


class FileManager():

  # dir_: str The absolute path to the source directory.
  def __init__(self, dir_ = ROOT_DIR):
    if not dir_:
      dir_ = os.path.abspath('.')
    if dir_[-1] != '/':
      dir_ += '/'
    self.dir = dir_

  ###
  ### PATH METHODS
  ###

  def pwd(self):
    return self.dir


  def get_path(self, filename):
    return os.path.join(self.dir, filename)

  # Resolves a user-supplied path.
  #
  # '/' means the sources root, a leading '/' means an absolute filesystem
  # path, a leading 'sources/' means a path below the sources root, and
  # anything else is relative to the current directory.
  def get_rooted(self, filename):
    if filename == '/':
      return ROOT_DIR
    if filename.startswith('/'):
      return filename
    if filename.startswith(SOURCES_PREFIX):
      return os.path.join(ROOT_DIR, filename.removeprefix(SOURCES_PREFIX))
    return os.path.join(self.dir, filename)

  # Changes the current directory.
  #
  # path: A path relative to the current directory ('..' included), or an
  # absolute path, or '/' to return to the sources root. Relative navigation
  # is normalised and cannot escape above the sources root.
  def cd(self, path: str) -> None:
    if path == '/':
      self.dir = ROOT_DIR
      return

    if path.startswith('/'):
      self.dir = path if path.endswith('/') else path + '/'
      return

    # Only clamp when we started inside the sources tree; the FileManager is
    # also pointed at arbitrary roots (notably by the tests).
    inside_root = self.dir.startswith(ROOT_DIR)
    new_dir = os.path.normpath(os.path.join(self.dir, path)) + '/'
    if inside_root and not new_dir.startswith(ROOT_DIR):
      new_dir = ROOT_DIR
    self.dir = new_dir

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
  # filename: The file to read, resolved by get_rooted.
  # Returns: The distinct lower-cased words in the file.
  # Raises: UnreadableSource if the file could not be read.
  def get_words(self, filename) -> list[str]:
    filename = self.get_rooted(filename)

    try:
      with open(filename, encoding='utf-8', errors='replace') as f:
        txt = f.read()
    except OSError:
      # `from None`: this replaces the OSError rather than being an accident
      # while handling it, so a stray traceback shows one exception, not two.
      raise UnreadableSource(f'Invalid filename: {filename}') from None

    txt = self.remove_gutenberg(txt)
    tokens = WORD_RE.findall(txt)
    # Lower-case before de-duplicating, so a word that appears both
    # capitalised and not is not twice as likely to be chosen.
    return sorted({t.lower() for t in tokens if any(c.isalpha() for c in t)})


  # Gets the contents of the directory passed in, or the current directory
  # if none is provided.
  #
  # Returns: String filepaths for all non-hidden folders and .txt files
  # found, or None if the directory could not be read.
  def ls(self, dir_ = None) -> list[str] | None:
    if dir_ is None:
      dir_ = self.dir
    try:
      entries = list(pathlib.Path(dir_).iterdir())
    except (FileNotFoundError, NotADirectoryError, PermissionError):
      return None
    results = [f for f in entries
               if (f.is_dir() and not f.name.startswith('.')) or f.suffix == '.txt']
    return [str(f) for f in results]


  # Get all .txt files in or below the current subdir.
  def get_txts(self, dir_ = None) -> list[str]:
    if dir_ is None:
      dir_ = self.dir
    return [str(path) for path in pathlib.Path(dir_).rglob('*.txt')]

  ###
  ### RAND FUNCTIONS
  ###

  # Gets a random .txt file, picking evenly between all files below the
  # current dir. Returns None if there are no .txt files below it.
  def rand_file(self, dir_ = None):
    txts = self.get_txts(dir_)
    if not txts:
      return None
    return random.choice(txts)

  # Gets a random file by choosing evenly among the entries of the current
  # subdir, then of the chosen subdir, and so on.
  #
  # Returns: The path of the chosen file, or None if none was found.
  def rand_dir(self) -> str | None:
    return self._rand_dir(self.dir)


  def _rand_dir(self, dir_) -> str | None:
    # Get all non-hidden folders and .txt files.
    options = self.ls(dir_)
    if not options:
      return None

    options = list(options)
    while options:
      choice = random.choice(options)
      fname = os.path.join(dir_, choice)
      if not os.path.isdir(fname):
        return str(fname)
      # A folder that turns out to hold no .txt files anywhere is skipped
      # rather than returning nothing.
      result = self._rand_dir(fname)
      if result is not None:
        return result
      options.remove(choice)
    return None
