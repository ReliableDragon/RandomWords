from file_command import FileCommand
from arg import Arg

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
      words = self.fm.get_words(args_[1])
    else:
      words = context.get('words')

    if not words:
      if len(args_) == 2:
        print(f'No words found in {args_[1]}; alias not created.')
      else:
        print('No words are loaded, so there is nothing to save.')
      return None

    if alias in context:
      overwrite = input('Alias exists. Overwrite? y/N')
      if not overwrite or not overwrite.lower().startswith('y'):
        return {}
    return {alias: words}
