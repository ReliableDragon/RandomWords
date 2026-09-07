import argparse

from file_manager import FileManager
from command_list import CommandList
from command_manager import CommandManager
from parser import Parser, unknown_command_result

DEFAULT_WORDS = 'sources/dicts/70k_words.txt'


class RandomWords():


  def __init__(self, file_manager, parser, command_manager):
    self.fm = file_manager
    self.parser = parser
    self.command_manager = command_manager


  def run(self, filename=DEFAULT_WORDS):
    load = self.command_manager.command_list.get_cmd('load')
    self.dispatch(load, [filename])
    print('Type a command, \'help\' for help, or \'quit\' to leave.')

    while True:
      try:
        cmd, args_ = self.parser.get_command()
        if cmd is None:
          self.show(unknown_command_result())
          continue
        if self.dispatch(cmd, args_):
          return
      except (EOFError, KeyboardInterrupt):
        # Ctrl-D or Ctrl-C leaves quietly rather than with a traceback.
        print()
        return
      except Exception as e:
        # A single bad command should never end the session.
        print(f'Error: {e}')


  # Runs one command and shows its result.
  #
  # Returns: True if the session should end.
  def dispatch(self, cmd, args_) -> bool:
    return self.show(self.command_manager.execute(cmd, args_))


  # Prints a result and asks its question, if it has one. This is the whole
  # of the terminal front end: everything else is shared with the API.
  #
  # Returns: True if the session should end.
  def show(self, result) -> bool:
    if result.message:
      print(result.message)
    if result.confirm:
      answer = input(result.confirm)
      if answer.lower().startswith('y'):
        self.command_manager.apply(result)
    return result.quit


def main():
  arg_parser = argparse.ArgumentParser(description='Get a random word from a book.')
  arg_parser.add_argument('filename', metavar='filename', nargs='?',
                          default=DEFAULT_WORDS,
                          help='file of words to load at startup')
  args = arg_parser.parse_args()

  fm = FileManager()
  cl = CommandList(fm)
  parser = Parser(cl)
  command_manager = CommandManager(cl)
  command_manager.initialize_commands()
  rw = RandomWords(fm, parser, command_manager)
  rw.run(args.filename)


if __name__ == '__main__':
  main()
