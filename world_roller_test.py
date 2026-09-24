import tempfile
import unittest
from pathlib import Path

from world_roller import load_facets, parse_facets, roll


HOW_TO = '''# Cheat Sheet

Concept
Behaviors (Multiple is good\\!)
Misconceptions
Interactions

## Methods/Tools
Not a facet
'''


class FixedRng:
  def __init__(self, interaction=False):
    self.interaction = interaction
    self.seen_weights = None

  def choice(self, values):
    return values[0]

  def choices(self, values, weights, k):
    self.seen_weights = dict(zip(values, weights))
    return [max(values, key=lambda value: weights[values.index(value)])]

  def random(self):
    return 0.0 if self.interaction else 1.0

  def sample(self, values, count):
    return values[:count]


class WorldRollerTest(unittest.TestCase):
  def setUp(self):
    self.entries = {
        'Flora/Fox.md': {
            'path': 'Flora/Fox.md', 'title': 'Fox', 'kind': 'Flora',
            'folder': 'Flora', 'biomes': [{'path': 'Locations/Biomes/Forest.md'}]},
        'Fauna/Owl.md': {
            'path': 'Fauna/Owl.md', 'title': 'Owl', 'kind': 'Fauna',
            'folder': 'Fauna', 'biomes': [{'path': 'Locations/Biomes/Forest.md'}]},
        'Geonomy/Stone.md': {
            'path': 'Geonomy/Stone.md', 'title': 'Stone', 'kind': 'Geonomy',
            'folder': 'Geonomy', 'biomes': []},
    }

  def test_parses_facet_section_and_live_file_edits(self):
    self.assertEqual(parse_facets(HOW_TO), ['Concept', 'Behaviors (Multiple is good!)',
                                           'Misconceptions', 'Interactions'])
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / 'How-To.md'
      path.write_text(HOW_TO, encoding='utf-8')
      self.assertEqual(load_facets(path)[0], 'Concept')
      path.write_text(HOW_TO.replace('Concept', 'Motivations'), encoding='utf-8')
      self.assertEqual(load_facets(path)[0], 'Motivations')

  def test_roll_weights_single_entry_toward_zero_inbound_and_returns_card(self):
    rng = FixedRng()
    result = roll(self.entries, {'Flora/Fox.md': [], 'Fauna/Owl.md': ['x']},
                  ['alpha', 'beta', 'gamma'], HOW_TO, rng=rng)
    self.assertGreater(rng.seen_weights['Flora/Fox.md'], rng.seen_weights['Fauna/Owl.md'])
    self.assertEqual(result['entry']['path'], 'Flora/Fox.md')
    self.assertEqual(result['entry']['title'], 'Fox')
    self.assertEqual(result['words'], ['alpha', 'beta'])

  def test_roll_can_choose_same_biome_interaction_with_two_distinct_cards(self):
    result = roll(self.entries, {}, ['alpha', 'beta'], HOW_TO,
                  rng=FixedRng(interaction=True))
    self.assertEqual(result['facet'], 'Interaction')
    self.assertEqual([card['path'] for card in result['entry']],
                     ['Fauna/Owl.md', 'Flora/Fox.md'])

  def test_supplied_facet_entry_and_words_are_retained(self):
    chosen_words = ['kept-word', 'other-kept-word']
    result = roll(self.entries, {}, ['unused'], HOW_TO, facet='Uses',
                  entry='Geonomy/Stone.md', words=chosen_words, rng=FixedRng())
    self.assertEqual(result, {
        'facet': 'Uses', 'entry': {
            'path': 'Geonomy/Stone.md', 'title': 'Stone', 'kind': 'Geonomy',
            'folder': 'Geonomy', 'biomes': []}, 'words': chosen_words})

  def test_interaction_requires_shared_canonical_biome(self):
    entries = {'Flora/Fox.md': self.entries['Flora/Fox.md'],
               'Geonomy/Stone.md': self.entries['Geonomy/Stone.md']}
    result = roll(entries, {}, ['alpha', 'beta'], HOW_TO,
                  rng=FixedRng(interaction=True))
    self.assertIsInstance(result['entry'], dict)


if __name__ == '__main__':
  unittest.main()
