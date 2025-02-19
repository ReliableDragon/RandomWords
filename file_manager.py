import os
import pathlib
import re
import logging
import random

logger = logging.getLogger(__name__)

ROOT_DIR = 'sources/'

class FileManager():


  def __init__(self, dir_ = 'sources/dicts', filename_ = '70k_words.txt'):
    self.dir = dir_
    self.filename = filename_

  ###
  ### PATH METHODS
  ###

  def get_path(self):
    return os.path.join(self.dir, self.filename)


  # Adds the provided path to the current subdir.
  #
  # path: A string name of a folder in the current subdir to append, or
  # '..' to move up, or '/' to return to the root.
  def cd(self, path: str) -> None:
    if path == '/':
      self.dir = ROOT_DIR
      return
    if path == '..':
      self.dir = self.dir.rsplit('/', 1)[0] + '/'
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
  def get_words(self) -> list[str]:
    try:
      f = open(self.get_path())
      txt = f.read()
      f.close()
      words = re.split('[^a-zA-Z]', txt)
      words = set(words)
      words.remove('')
      words = list(words)
      return words

    except OSError:
      print('Invalid filename!')
      return []


  # Gets the contents of the current subdir.
  #
  # Returns: The Path objects in the current subdir.
  def ls(self) -> list[pathlib.Path]:
    results = []
    for f in pathlib.Path(self.dir).iterdir():
      if (f.is_dir() and str(f)[0] != '.'):
        results.append(f)
      elif f.suffix == '.txt':
        results.append(f)
    return results


  # Get all .txt files in current subdir.
  def get_txts(self) -> list[str]:
    matching_files = []
    for path in pathlib.Path(self.dir).rglob('*.txt'):
      matching_files.append(str(path))
    return matching_files

  ###
  ### RAND FUNCTIONS
  ###

  # Gets a random option by picking randomly from the objects in
  # the current subdir at each step.
  #
  # Returns: The string name of the chosen file.
  def rand_dir(self) -> str:
    curr_dir = self.dir
    choice = self._rand_dir()
    self.dir = curr_dir
    return choice


  def _rand_dir(self) -> str:
    # Get all non-hidden folders and .txt files
    options = self.ls()
    # Return if no files found
    if not options:
      return ''

    choice = random.choice(options)
    
    if choice.is_dir():
      self.cd(choice.name)
      return self._rand_dir()
    else:
      return str(choice.name)
