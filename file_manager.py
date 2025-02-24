import os
import pathlib
import re
import logging
import random

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath('sources/') + '/'

class FileManager():


  # dir_: str The absolute path to the source directory.
  def __init__(self, dir_ = os.path.abspath('sources/dicts/')):
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
      
    if path[-1] != '/':
      path += '/'
    if self.dir[-1] != '/':
      self.dir += '/'
    self.dir += path

  ###
  ### LIST METHODS
  ###

  # Gets all of the words present in a file.
  #
  # filename: The file to try to get the words from. 
  # Returns: All the words in the file, deduped, without order.
  def get_words(self, filename) -> list[str]:
    try:
      f = open(filename)
      txt = f.read()
      f.close()
      words = re.split('[^a-zA-Z]', txt)
      words = set(words)
      words.remove('')
      words = list(words)
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
    for f in file_list:
      if (f.is_dir() and str(f)[0] != '.'):
        results.append(f)
      elif f.suffix == '.txt':
        results.append(f)
    return [str(f) for f in results]


  # Get all .txt files in or below current subdir.
  def get_txts(self) -> list[str]:
    matching_files = []
    for path in pathlib.Path(self.dir).rglob('*.txt'):
      matching_files.append(str(path))
    return matching_files

  ###
  ### RAND FUNCTIONS
  ###

  # Gets a random .txt file, picking evenly
  # between all files below the current dir.
  def rand_file(self):
    txts = self.get_txts()
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
