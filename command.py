from typing import List, Callable
from abc import ABC, abstractmethod

from arg import Arg

class Command():


  def __init__(self, name: str, args: list[Arg]):
    self.name = name
    self.args = args


  def populate_args(self, values: list):
    if len(values) != len(self.args):
      raise ValueError(f"Number of values did not match number of args!\nvalues: {values}\nargs: {self.args}")
    for value, arg in zip(values, self.args):
      arg.populate(value)


  def execute(self):
    pass


  def __str__(self):
    return f"Command({self.name}){[str(arg) for arg in self.args]}"
