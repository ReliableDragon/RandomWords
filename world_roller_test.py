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
    self.seen_weights = dict(zip(values, weights, strict=False))
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
            'folder': 'Geonomy', 'biomes': [], 'from_targets': [],
            'link': 'Geonomy/Stone'},
        'words': chosen_words})

  def test_interaction_requires_shared_canonical_biome(self):
    entries = {'Flora/Fox.md': self.entries['Flora/Fox.md'],
               'Geonomy/Stone.md': self.entries['Geonomy/Stone.md']}
    result = roll(entries, {}, ['alpha', 'beta'], HOW_TO,
                  rng=FixedRng(interaction=True))
    self.assertIsInstance(result['entry'], dict)

  def test_random_roll_excludes_templates_ideas_and_root_notes(self):
    entries = dict(self.entries)
    for path in ('Templates/Creature Template.md', 'Ideas/Ideas.md', 'How-To.md', 'Tags.md'):
      folder, _, name = path.rpartition('/')
      entries[path] = {'path': path, 'title': name[:-3], 'kind': folder.split('/')[0],
                       'folder': folder, 'biomes': []}
    rng = FixedRng()
    roll(entries, {}, ['alpha', 'beta'], HOW_TO, rng=rng)
    self.assertEqual(set(rng.seen_weights), set(self.entries))

  def test_random_roll_skips_story_folder_scenes(self):
    entries = dict(self.entries)
    entries['Story/Scene.md'] = {'path': 'Story/Scene.md', 'title': 'Scene', 'kind': 'Story',
                                 'folder': 'Story', 'biomes': []}
    rng = FixedRng()
    roll(entries, {}, ['alpha', 'beta'], HOW_TO, rng=rng, story_folders=('Story',))
    self.assertEqual(set(rng.seen_weights), set(self.entries))

  def test_interaction_pairs_ignore_non_world_notes(self):
    entries = {
        'Flora/Fox.md': self.entries['Flora/Fox.md'],
        'Templates/T.md': {'path': 'Templates/T.md', 'title': 'T', 'kind': 'Templates',
                           'folder': 'Templates',
                           'biomes': [{'path': 'Locations/Biomes/Forest.md'}]},
    }
    result = roll(entries, {}, ['alpha', 'beta'], HOW_TO, rng=FixedRng(interaction=True))
    self.assertEqual(result['entry']['path'], 'Flora/Fox.md')

  def test_only_non_world_notes_is_an_error_but_explicit_entry_is_allowed(self):
    entries = {'Tags.md': {'path': 'Tags.md', 'title': 'Tags', 'kind': '',
                           'folder': '', 'biomes': []}}
    with self.assertRaises(ValueError):
      roll(entries, {}, ['alpha', 'beta'], HOW_TO, rng=FixedRng())
    result = roll(entries, {}, ['alpha', 'beta'], HOW_TO, entry='Tags.md', rng=FixedRng())
    self.assertEqual(result['entry']['path'], 'Tags.md')

  def test_thin_biomes_get_a_mild_bonus_on_top_of_orphan_weight(self):
    def item(path, biome):
      return {'path': path, 'title': path, 'kind': 'Flora', 'folder': 'Flora',
              'biomes': [{'path': biome}] if biome else []}
    entries = {'Flora/a.md': item('Flora/a.md', 'Locations/Biomes/Big.md'),
               'Flora/b.md': item('Flora/b.md', 'Locations/Biomes/Big.md'),
               'Flora/c.md': item('Flora/c.md', 'Locations/Biomes/Big.md'),
               'Flora/d.md': item('Flora/d.md', 'Locations/Biomes/Big.md'),
               'Flora/thin.md': item('Flora/thin.md', 'Locations/Biomes/Thin.md'),
               'Flora/none.md': item('Flora/none.md', None)}
    rng = FixedRng()
    roll(entries, {}, ['alpha', 'beta'], HOW_TO, rng=rng)
    weights = rng.seen_weights
    self.assertEqual(weights['Flora/a.md'], 1.0)
    self.assertEqual(weights['Flora/none.md'], 1.0)
    self.assertGreater(weights['Flora/thin.md'], 1.0)
    self.assertLessEqual(weights['Flora/thin.md'], 1.5)
    # Inbound links still lower a thin entry's odds.
    rng = FixedRng()
    roll(entries, {'Flora/thin.md': ['x', 'y', 'z']}, ['alpha', 'beta'], HOW_TO, rng=rng)
    self.assertLess(rng.seen_weights['Flora/thin.md'], rng.seen_weights['Flora/a.md'])

  def test_cards_carry_biomes_and_from_targets_from_direct_places(self):
    places = {'Flora/Fox.md': ('Locations/Places/Glade.md',)}
    result = roll(self.entries, {}, ['alpha', 'beta'], HOW_TO, entry='Flora/Fox.md',
                  rng=FixedRng(), direct_places=places)
    self.assertEqual(result['entry']['biomes'], ['Locations/Biomes/Forest.md'])
    self.assertEqual(result['entry']['from_targets'], ['Locations/Places/Glade.md'])
    fallback = roll(self.entries, {}, ['alpha', 'beta'], HOW_TO, entry='Fauna/Owl.md',
                    rng=FixedRng(), direct_places=places)
    self.assertEqual(fallback['entry']['from_targets'], ['Locations/Biomes/Forest.md'])

  def test_link_comes_from_the_supplied_resolver(self):
    result = roll(self.entries, {}, ['alpha', 'beta'], HOW_TO, entry='Flora/Fox.md',
                  rng=FixedRng(), link_of=lambda path: 'Fox')
    self.assertEqual(result['entry']['link'], 'Fox')


if __name__ == '__main__':
  unittest.main()
