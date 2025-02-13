import re
import random
import argparse
import os

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
  quits = ['exit', 'no', 'q']
  files = sorted(list(os.listdir()))
  while True:
    if cmd == '':
      print(random.choice(words))
    elif cmd.lower() in quits:
      exit()
    elif cmd.lower() == 'ls':
      for fn in sorted(list(os.listdir())):
        print(fn)
    elif cmd.lower().startswith('add '):
      fname = cmd[4:]
      print('Adding in ' + fname)
      words = fetch_words(fname)
    elif cmd.lower() in ['random', 'rand', 'r']:
      fname = random.choice(files)
      print('Opening ' + fname)
      words = fetch_words(fname)
    else:
      print('Opening ' + cmd)
      words = fetch_words(cmd)
    cmd = input('')

wfb(args.filename)
