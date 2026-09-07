from dataclasses import dataclass, field


# What a command hands back to whoever ran it.
#
# The terminal front end prints `message` and asks `confirm`; an HTTP front
# end serialises `message` and `data` and maps `ok` onto a status code. The
# command never learns which of the two is calling it.
@dataclass
class CommandResult:

  # False marks a user error, such as a bad path or an unknown alias.
  # An exception is a bug and is not represented here.
  ok: bool = True

  # The human-readable line a terminal prints.
  message: str = ''

  # Structured payload for an API. Never carries a whole word pool.
  data: dict | None = None

  # Context entries to merge. Withheld while `confirm` is set.
  updates: dict = field(default_factory=dict)

  # A question the front end must ask before `updates` are applied.
  confirm: str = ''

  # Ends the session. Only the terminal front end honours it.
  quit: bool = False


  @classmethod
  def fail(cls, message):
    return cls(ok=False, message=message)

