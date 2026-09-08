from command import Command
from command_result import CommandResult

class Dump(Command):

  @staticmethod
  def cmd_name():
    return 'dump'

  def overview(self):
    return 'dump [all]'

  # 'dump' takes at most one argument. execute() only treats it specially
  # when it is 'all' or 'full'; anything else is accepted here too and
  # simply ignored below, which is the behaviour this replaces (the old
  # arg-built matches() didn't check the argument's spelling either).
  def matches(self, line):
    return self.check_match(r'dump( [^ ]+)?', line)

  def execute(self, args_, context):
    if args_ and args_[0].lower() in ['all', 'full']:
      return CommandResult(message=f'context: {context}')
    if not context:
      return CommandResult(message='Nothing is loaded.')
    lines = []
    pools = []
    for name, words in context.items():
      label = 'words (active pool)' if name == 'words' else name
      lines.append(f'{label}: {len(words)} words')
      pools.append({'name': name, 'size': len(words)})
    return CommandResult(message='\n'.join(lines), data={'pools': pools})
