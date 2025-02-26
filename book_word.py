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
parser.add_argument('filename', metavar='filename', nargs='?',
                    help='filename to get the word from')
args = parser.parse_args()


class RandomWords():


  def __init__(self, file_manager, parser, command_manager):
    self.cmd = 'word' 
    self.fm = file_manager
    self.parser = parser
    self.command_manager = command_manager


  def run(self):
    result = None
    self.command_manager.execute(self.command_manager.command_list.get_cmd('load'), ['sources/dicts/70k_words.txt'])
    print('Type a command, or \'help\' for help.')
    while result != 'quit':
      cmd, args_ = self.parser.get_command()
      result = self.command_manager.execute(cmd, args_)

      

  # def wfb(fn):
      # Add another file's words into the current pool.
  #   elif cmd.lower().startswith('add '):
  #     fname = subdir + cmd[4:]
  #     print('Adding in ' + fname)
  #     words = fetch_words(fname)


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
