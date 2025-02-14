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
  while True:
    if cmd == '':
      print(random.choice(words))
    elif cmd.lower() in quits:
      exit()
    elif cmd.lower() == 'ls':
      for fname in files:
        print(fname)
    elif cmd.lower().startswith('cd '):
      subdir = cmd[3:]
      print(subdir)
      if subdir == '/':
        subdir = ''
      print('Setting directory to "' + subdir + '".')
      files = get_txts(subdir)
    elif cmd.lower().startswith('add '):
      fname = subdir + cmd[4:]
      print('Adding in ' + fname)
      words = fetch_words(fname)
    elif cmd.lower() in ['random', 'rand', 'r']:
      fname = random.choice(files)
      print('Opening ' + fname)
      words = fetch_words(fname)
    else:
      fname = subdir + cmd
      print('Opening ' + fname)
      words = fetch_words(fname)
    cmd = input('')

wfb(args.filename)
