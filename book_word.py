import re
import random
import argparse
import os

from pathlib import Path
from file_manager import FileManager
from command_list import CommandList
from command_manager import CommandManager
from parser import Parser

parser = argparse.ArgumentParser(description='Get a random word from a book.')
parser.add_argument('filename', metavar='filename',
                    help='filename to get the word from')
args = parser.parse_args()

QUITS = ['exit', 'no', 'q']
RAND_CMDS = ['random', 'rand', 'r']
RAND_DIR_CMDS = ['random_dir', 'rand_dir', 'rd']
COMMANDS = ['word', 'ls', 'cd'] + QUITS + RAND_CMDS + RAND_DIR_CMDS


class RandomWords():


  def __init__(self, file_manager, parser, command_manager):
    self.cmd = 'word' 
    self.fm = file_manager
    self.parser = parser
    self.command_manager = command_manager


  def run(self):
    result = None
    while result != 'quit':
      cmd, args_ = self.parser.get_command()
      result = self.command_manager.execute(cmd, args_)

      

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
  cl = CommandList(fm)
  parser = Parser(cl)
  command_manager = CommandManager(cl)
  command_manager.initialize_commands()
  rw = RandomWords(fm, parser, command_manager)
  rw.run()


if __name__ == '__main__':
  main()
