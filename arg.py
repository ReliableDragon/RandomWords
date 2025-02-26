from typing import Any

class Arg():
  

  def __init__(self, type_: type, optional: bool = False, repeated=False):
    self.type = type_
    self.optional = optional
    self.repeated = repeated


  def validate(self, value):
    if value == None and self.optional:
      return True
    if type(value) != self.type:
      return False
    return True

  def __str__(self):
    result = f"Arg[{self.type.__name__}"
    if self.optional:
      result += ', opt'
    if self.repeated:
      result += ', rep'
    result += ']'
    return result

