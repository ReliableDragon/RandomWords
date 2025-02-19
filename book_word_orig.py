import re
import random
import argparse
import os

from pathlib import Path

parser = argparse.ArgumentParser(description='Get a random word from a book.')
parser.add_argument('filename', metavar='fn',
                    help='filename to get the word from')
args = parser.parse_args()

def get_words(fn):
  f = open(fn)
  txt = f.read()
  f.close()
  words = re.split('[^a-zA-Z]', txt)
  words = set(words)
  words.remove('')
  words = list(words)
  return words

def txt(fn):
  if not fn.endswith('.txt'):
    return fn + '.txt'
  return fn

def rand_dir(subdir='.'):
  options = [x for x in Path(subdir).iterdir() if (x.is_dir() and str(x)[0] != '.') or x.suffix == '.txt']
  if not options:
    return ''
  choice = random.choice(options)
  if choice.is_dir():
    subdir = subdir + str(choice) if subdir != '.' else str(choice)
    return rand_dir(subdir)
  else:
    return str(choice)

def get_txts(subdir='.'):
  matching_files = []
  for path in Path(subdir).rglob('*.txt'):
    matching_files.append(str(path))
  return matching_files

def fetch_words(fname):
  try:
    words = get_words(txt(fname))
    return words
  except OSError:
    print('Invalid filename!')
    return []

def wfb(fn):
  words = get_words(fn)
  cmd = ''
  subdir = ''
  quits = ['exit', 'no', 'q']
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

wfb(args.filename)
