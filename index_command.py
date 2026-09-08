from command import Command


# A Command that holds the library index, the way FileCommand holds the file
# manager.
#
# The index is built on first use rather than at startup, so a command here
# calls `ready()` before it reads anything and reports the one failure that
# can produce.
class IndexCommand(Command):

  def __init__(self, index):
    super().__init__()
    self.index = index


  # True when the index can be queried. The call builds it if this is the
  # first command that has needed it, which on a cold cache takes seconds.
  def ready(self) -> bool:
    return self.index.ensure_ready()


  # The failure to return when it could not be built at all.
  @staticmethod
  def not_ready_message() -> str:
    return 'The library index could not be built, so there is nothing to compare against.'
