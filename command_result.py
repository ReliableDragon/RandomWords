from dataclasses import dataclass, field
from typing import Callable


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

  # Occurrence counts to store for pools (pool_name -> dict[str, int]).
  counts: dict = field(default_factory=dict)

  # Context entries to forget. Applied with `updates` and under the same
  # rules, so a failed or unconfirmed command removes nothing.
  removes: list = field(default_factory=list)

  # A question the front end must ask before `updates` are applied.
  confirm: str = ''

  # Ends the session. Only the terminal front end honours it.
  quit: bool = False

  # A callback for a side effect that has to wait for a yes and cannot be
  # expressed as an `updates` merge -- writing a file, say. It takes no
  # arguments and returns the message to report for having done it.
  # `CommandManager.apply` calls this once, after merging `updates`, and
  # only when `ok` is true; it is the one point a yes reaches regardless of
  # which front end asked, so a command that sets this runs its side effect
  # there rather than in `execute`, which may run again (harmlessly, since
  # nothing has been confirmed yet) before an answer exists. Most commands
  # leave this unset: merging `updates` into the context is itself the
  # whole of what confirming them means.
  on_confirm: Callable[[], str] | None = None


  @classmethod
  def fail(cls, message):
    return cls(ok=False, message=message)

