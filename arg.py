from typing import Any

class Arg():
  

  def __init__(self, type_: type, value_: Any = None, name_: str = ''):
    self.type = type_
    self.value = value_
    self.name = name_ 


  def populate(self, value):
    if type(value) != self.type:
      raise ValueError(f"Incorrect type provided for Arg {self.name}: Got '{value}' of type {type(value)}, but expected a value of type {self.type}.")
    self.value = value


  def get(self):
    return self.value


  def __str__(self):
    return f"Arg({self.name})[{self.type.__name__}]: {self.value}"

