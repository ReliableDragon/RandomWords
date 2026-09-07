import logging
import threading

from command_list import CommandList
from command_manager import CommandManager
from command_result import CommandResult
from parser import Parser, unknown_command_result

logger = logging.getLogger(__name__)


class Session():
  """One person's word pools, and the commands that change them.

  This is the whole of a session now that the file manager keeps no working
  directory: a context of pools and nothing else.
  """

  def __init__(self, file_manager):
    self.fm = file_manager
    self.commands = CommandList(file_manager)
    self.manager = CommandManager(self.commands)
    self.manager.initialize_commands()
    self.parser = Parser(self.commands)
    # Where each pool came from, for display only. Kept beside the context
    # rather than in it, because the context holds word lists and every
    # command in the language expects that.
    self.sources = {}
    # Guards the context. Held across a command rather than only across the
    # merge, because commands read the context as well as write it. The
    # cache in word_cache.py is what keeps the slow case out of here: a
    # parse behind this lock would queue every other request.
    self._lock = threading.RLock()


  # Runs a named command with already-parsed arguments.
  def run(self, name: str, args: list) -> CommandResult:
    with self._lock:
      return self.manager.execute(self.commands.get_cmd(name), args)


  # Runs a line of the command language, the way the terminal does.
  def run_line(self, line: str) -> CommandResult:
    cmd, args_ = self.parser.parse(line)
    if cmd is None:
      return unknown_command_result()
    with self._lock:
      return self.manager.execute(cmd, args_)


  # Applies updates a command withheld pending a confirmation.
  def apply(self, result: CommandResult) -> CommandResult:
    with self._lock:
      return self.manager.apply(result)


  # Records the text a pool was read from, so the page can name it later.
  def note_source(self, pool: str, source: str) -> None:
    with self._lock:
      self.sources[pool] = source


  @property
  def context(self) -> dict:
    return self.manager.context


  # Every pool with its size. Never the words themselves: the largest is six
  # megabytes of JSON, to support a draw that takes a microsecond here.
  def pools(self) -> list[dict]:
    with self._lock:
      return [{'name': name, 'size': len(words), 'active': name == 'words',
               'source': self.sources.get(name)}
              for name, words in self.manager.context.items()]


class SessionStore():
  """Where identity will go, and the only place it will have to go.

  Today there is one session and everybody gets it, which is right for a tool
  bound to loopback. Everything above takes a session as an argument, so
  giving people their own is a change to this class and to nothing else.
  """

  def __init__(self, file_manager):
    self.fm = file_manager
    self._session = Session(file_manager)


  def for_request(self, headers=None) -> Session:
    return self._session
