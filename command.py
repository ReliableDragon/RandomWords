from typing import List, Callable
from abc import ABC, abstractmethod

from arg import Arg

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
    if len(values) != len(self.args):
      raise ValueError(f"Number of values did not match number of args!\nvalues: {values}\nargs: {self.args}")
    for value, arg in zip(values, self.args):
      if type(value) != arg:
        raise ValueError(f"Got incorrect arg type(s)!\nExpected: {self.args}\nBut was: {[type(v) for v in values]}")

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
