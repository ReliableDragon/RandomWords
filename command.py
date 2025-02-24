import re
import logging
import itertools

from typing import List, Callable
from abc import ABC, abstractmethod

from arg import Arg

logger = logging.getLogger(__name__)

DEFAULT_COMMAND = 'ls'

class Command():


  def __init__(self):
    self.name = self.cmd_name()
    self.args = self.cmd_args()

  
  @classmethod
  def create(cls, name, args_):
    new_cmd = cls()
    new_cmd.name = name
    new_cmd.args = args_
    return new_cmd


  def validate_args(self, values: list):
    for value, arg in itertools.zip_longest(values, self.args):
      if arg == None or not arg.validate(value):
        raise ValueError(f"Got incorrect arg type(s)!\nExpected: {[str(arg) for arg in self.args]}\nBut was: {[type(v) for v in values]}")

  def check_match(self, regex, line):
    line = line.lower()
    match = re.fullmatch(regex, line)
    if not match:
      return False
    else:
      return True

  # Determine whether this command is being invoked. If this method
  # is not overridden, defaults to the command's name plus the
  # rest of a line if it has arguments.
  def matches(self, line):
    regex = self.name
    if self.args:
      regex += r' .*'
    return self.check_match(regex, line)

  def parse_args(self, line):
    if not self.args: 
      return []
    return line.split(' ')[1:]

  def execute(self, args_, context):
    pass

  @staticmethod
  def cmd_name():
    pass

  @staticmethod
  def cmd_args():
    pass


  def __str__(self):
    return f"Command({self.name}){[str(arg) for arg in self.args]}"
