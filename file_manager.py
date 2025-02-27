import os
import pathlib
import re
import logging
import random

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath('sources/') + '/'

class FileManager():


  # dir_: str The absolute path to the source directory.
  def __init__(self, dir_ = os.path.abspath('sources/')):
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

  def get_rooted(self, filename):
    if filename == '/':
      return ROOT_DIR
    if filename.startswith('/'):
      return filename

    # This will leave the initial '/'.
    relative_root = ROOT_DIR.removeprefix(os.path.abspath('.'))
    # Remove initial '/'
    relative_root = relative_root[1:]
    if filename.startswith(relative_root):
      relative_filename = filename.removeprefix(relative_root)
      return os.path.join(ROOT_DIR, relative_filename)
    return os.path.join(self.dir, filename)

  # Adds the provided path to the current subdir.
  #
  # path: A string name of a folder in the current subdir to append, or
  # '..' to move up, or '/' to return to the root.
  def cd(self, path: str) -> None:
    assert self.dir.endswith('/'), 'FileManager directory doesn\'t end with a slash -- this will cause issues!'
    if path == '..':
      self.dir = self.dir.rsplit('/', 2)[0] + '/'
      if not self.dir.startswith(ROOT_DIR):
        self.dir = ROOT_DIR
      return

    if path[-1] != '/':
      path += '/'

    if path == '/':
      self.dir = ROOT_DIR
      return

    if path.startswith('/'):
      self.dir = path
      return
      
    self.dir += path

  ###
  ### LIST METHODS
  ###

  # Gets all of the words present in a file.
  #
  # filename: The file to try to get the words from. 
  # Returns: All the words in the file, deduped, without order.
  def remove_gutenberg(self, txt):
    header = '*** START OF THE PROJECT GUTENBERG EBOOK'
    footer = '*** END OF THE PROJECT GUTENBERG EBOOK'
    if header not in txt:
      return txt

    index = 0
    out_txt = ''
    while header in txt[index:]:
      header_start = txt.index(header, index)
      header_end = txt.index('***', header_start+1)
      footer_start = txt.index(footer, header_end)
      out_txt += txt[header_end+3:footer_start]
      index = footer_start+1
    return out_txt
    

  def get_words(self, filename) -> list[str]:
    filename = self.get_rooted(filename)
      
    try:
      with open(filename) as f:
        txt = f.read()
      txt = self.remove_gutenberg(txt)

      words = re.split('[^\w\-\—\–]', txt)
      words = set(words)

      if '' in words:
        words.remove('')
      words = filter(lambda a: not a.isnumeric(), words)
      words = list(words)
      words = [w.lower() for w in words]
      return words

    except OSError:
      print(f'Invalid filename: {filename}')
      return []


  def get_relative_name(self, filepath):
    return filepath.name.removeprefix(self.dir)

  # Gets the contents of the directory passed in, or
  # the current directory if none is provided.
  #
  # Returns: String filepaths for all folders and
  # .txt files found.
  def ls(self, dir_ = None) -> list[str]:
    assert self.dir.endswith('/'), 'LS was called while FileManager directory did not end in "/" -- this will cause problems!'
    if dir_ == None:
      dir_ = self.dir
    results = []
    file_list = pathlib.Path(dir_).iterdir()
    try:
      for f in file_list:
        if (f.is_dir() and str(f)[0] != '.'):
          results.append(f)
        elif f.suffix == '.txt':
          results.append(f)
      return [str(f) for f in results]
    except FileNotFoundError:
      return None


  # Get all .txt files in or below current subdir.
  def get_txts(self, dir_ = None) -> list[str]:
    if dir_ == None:
      dir_ = self.dir
    matching_files = []
    for path in pathlib.Path(dir_).rglob('*.txt'):
      matching_files.append(str(path))
    return matching_files

  ###
  ### RAND FUNCTIONS
  ###

  # Gets a random .txt file, picking evenly
  # between all files below the current dir.
  def rand_file(self, dir_ = None):
    txts = self.get_txts(dir_)
    file = random.choice(txts)
    return file

  # Gets a random option by picking randomly from the objects in
  # the current subdir at each step.
  #
  # Returns: The string name of the chosen file.
  def rand_dir(self) -> str:
    curr_dir = self.dir
    choice = self._rand_dir(curr_dir)
    return choice


  def _rand_dir(self, dir_) -> str:
    # Get all non-hidden folders and .txt files
    options = self.ls(dir_)
    # Return if no files found
    if not options:
      return ''

    choice = random.choice(options)
    fname = os.path.join(dir_, choice)
    
    if os.path.isdir(fname):
      return self._rand_dir(fname)
    else:
      return str(fname)
