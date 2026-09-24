from command import Command
from command_result import CommandResult
from sampling import sample_words


class WeightedWord(Command):

  @staticmethod
  def cmd_name():
    return 'weighted_word'

  def overview(self):
    return 'weighted_word [w, weighted, oword] [N]: draw N words weighted by occurrence count'

  def matches(self, line):
    return self.check_match(r'(weighted_word|weighted|oword|w)( \d+)?', line)

  def parse_args(self, line):
    parts = line.strip().split()
    if len(parts) > 1 and parts[1].isnumeric():
      return [int(parts[1])]
    return []

  def execute(self, args_, context):
    words = context.get('words')
    if not words:
      return CommandResult.fail('No words are loaded. Use load, r or dr first.')
    num = args_[0] if args_ else 1
    pool_counts = getattr(context, 'counts', {}).get('words')
    drawn = sample_words(words, pool_counts or {}, num, weighted=True)
    data = {'drawn': drawn}
    if pool_counts is not None:
      data['counts'] = {w: pool_counts.get(w, 1) for w in drawn}
    return CommandResult(message=' '.join(drawn), data=data)
