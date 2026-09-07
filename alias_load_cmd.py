from file_command import FileCommand
from command_result import CommandResult
from arg import Arg
from file_manager import UnreadableSource

OVERWRITE_QUESTION = 'Alias exists. Overwrite? y/N'

class AliasLoad(FileCommand):

  @staticmethod
  def cmd_name():
    return 'alias_load'

  @staticmethod
  def cmd_args():
    return [Arg(str), Arg(str, optional=True)]

  def overview(self):
    return 'alias_load [alias, al] <name> [file.txt]'

  def matches(self, line):
    regex = r'(alias_load|alias|al) [\w_]+( [\w_.\/]+)?'
    return self.check_match(regex, line)

  def parse_args(self, line):
    return line.strip().split(' ')[1:]

  def execute(self, args_, context):
    alias = args_[0]
    if len(args_) == 2:
      # get_words resolves the path itself.
      try:
        words = self.fm.get_words(args_[1])
      except UnreadableSource as e:
        return CommandResult.fail(
            f'{e}\nNo words found in {args_[1]}; alias not created.')
    else:
      words = context.get('words')

    if not words:
      if len(args_) == 2:
        return CommandResult.fail(f'No words found in {args_[1]}; alias not created.')
      return CommandResult.fail('No words are loaded, so there is nothing to save.')

    updates = {alias: words}
    data = {'pool': alias, 'size': len(words)}

    if alias in context:
      # The command does not ask; it says what needs asking and hands back
      # the answer it would apply. The manager withholds the updates until
      # a front end brings back a yes, so a terminal can prompt and an HTTP
      # client can retry with force, and this code never learns which.
      return CommandResult(updates=updates, data=data,
                           confirm=OVERWRITE_QUESTION)

    return CommandResult(updates=updates, data=data)
