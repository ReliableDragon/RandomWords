import re
import random
import argparse
import os

from pathlib import Path
from file_manager import FileManager

parser = argparse.ArgumentParser(description='Get a random word from a book.')
parser.add_argument('filename', metavar='filename',
                    help='filename to get the word from')
args = parser.parse_args()

QUITS = ['exit', 'no', 'q']
RAND_CMDS = ['random', 'rand', 'r']
RAND_DIR_CMDS = ['random_dir', 'rand_dir', 'rd']
COMMANDS = ['word', 'ls', 'cd'] + QUITS + RAND_CMDS + RAND_DIR_CMDS


class RandomWords():


  def __init__(self, file_manager):
    self.cmd = 'word' 
    self.fm = file_manager
    self.dispatch = {
      'word': self.word_fn,
      'ls': self.ls_fn,
      'cd': self.cd_fn,
      'random': self.rand_fn,
      'rand': self.rand_fn,
      'r': self.rand_fn,
      'random_dir': self.randdir_fn,
      'rand_dir': self.randdir_fn,
      'rd': self.randdir_fn,
    }


  def word_fn(self):
    pass


  def ls_fn(self):
    pass


  def cd_fn(self):
    pass


  def rand_fn(self):
    pass


  def randdir_fn(self):
    pass


  def get_cmd(self):
    while True:
      full_cmd = input('Input a command, or type "help" for help.')
      cmd_frags = full_cmd.split(' ')
      if cmd_frags[0] not in self.dispatch + QUITS:
        print("I'm sorry, I don't understand.")
        continue
      

      


  def repl(self):
    while True:
      cmd, args = self.get_cmd()
      if cmd in QUITS:
        break
      
     


  def wfb(fn):
    words = get_words(fn)
    files = get_txts()
    default_cmd = 'word'
    while True:
      cmd = input('')
      if cmd == '':
	cmd = default_cmd

      # Print a random word from current file if no command given
      if cmd == 'word':
	print(random.choice(words))

      # Exit commands
      elif cmd.lower() in quits:
	exit()

      # List available files in current subdirectory
      elif cmd.lower() == 'ls':
	for fname in files:
	  print(fname)

      # Change to a new subdirectory
      elif cmd.lower().startswith('cd '):
	subdir = cmd[3:]
	print(subdir)
	if subdir == '/':
	  subdir = ''
	print('Setting directory to "' + subdir + '".')
	files = get_txts(subdir)

      # Add another file's words into the current pool.
      elif cmd.lower().startswith('add '):
	fname = subdir + cmd[4:]
	print('Adding in ' + fname)
	words = fetch_words(fname)

      # Select a random file from all possible files below the current subdirectory.
      elif cmd.lower() in ['random', 'rand', 'r']:
	fname = random.choice(files)
	print('Opening ' + fname)
	words = fetch_words(fname)

      # Select a random file by picking one option at each layer, and recursing.
      elif cmd.lower() in ['random_dir', 'rand_dir', 'rd']:
	fname = rand_dir(subdir)
	print('Opening ' + fname)
	words = fetch_words(fname)

      # If no other command, assume we've been given a filename to open.
      else:
	fname = subdir + cmd
	print('Opening ' + fname)
	words = fetch_words(fname)


def main():
  fm = FileManager()
  rw = RandomWords(fm)
  rw.repl()


if __name__ == '__main__':
  main()
