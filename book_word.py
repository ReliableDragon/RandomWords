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

def wfb(fn):
  words = get_words(fn)
  cmd = ''
  quits = ['exit', 'no', 'q']
  while True:
    if cmd == '':
      print(random.choice(words))
    elif cmd.lower() in quits:
      exit()
    elif cmd.lower() == 'ls':
      for fn in sorted(list(os.listdir())):
        print(fn)
    elif cmd.lower().startswith('add '):
      words += get_words(txt(cmd[4:]))
    else:
      try:
        print('Opening ' + cmd)
        words = get_words(txt(cmd))
        cmd = ''
        continue
      except OSError:
        print('Invalid filename!')
    cmd = input('')

wfb(args.filename)
