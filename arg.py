from typing import Any

class Arg():
  

  def __init__(self, type_: type, optional: bool = False):
    self.type = type_
    self.optional = optional


  def validate(self, value):
    if value == None and self.optional:
      return True
    if type(value) != self.type:
      return False
    return True

  def __str__(self):
    return f"Arg[{self.type.__name__}](optional: {self.optional})"

