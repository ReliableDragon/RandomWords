import unittest

from fake_file_manager import FakeFileManager
from session import Session
from web_routes import Request, dispatch
from word_cache import CachingFileManager


class WebRoutesTest(unittest.TestCase):

  def setUp(self):
    self.td = FakeFileManager()
    self.td.__enter__()
    self.fm = CachingFileManager(self.td.root)
    self.session = Session(self.fm)

  def tearDown(self):
    self.td.__exit__(None, None, None)

  def go(self, method, path, query=None, body=None):
    return dispatch(Request(method, path, query or {}, body or {},
                            session=self.session, fm=self.fm))

  def load_a_text(self):
    return self.go('POST', '/api/pools/load',
                   body={'source': self.td.td.tf1_path})

  ###
  ### library
  ###

  def test_library_lists_the_root(self):
    response = self.go('GET', '/api/library')

    self.assertEqual(response.status, 200)
    paths = {e['path'] for e in response.payload['entries']}
    self.assertEqual(paths, {self.td.td.tf1_path, self.td.td.d2_path})

  def test_library_counts_texts_in_a_folder(self):
    response = self.go('GET', '/api/library')
    folder = next(e for e in response.payload['entries'] if e['is_dir'])
    self.assertEqual(folder['texts'], 4)

  def test_library_reports_a_size_only_once_read(self):
    response = self.go('GET', '/api/library')
    text = next(e for e in response.payload['entries'] if not e['is_dir'])
    self.assertIsNone(text['size'])

    self.load_a_text()

    response = self.go('GET', '/api/library')
    text = next(e for e in response.payload['entries'] if not e['is_dir'])
    self.assertEqual(text['size'], 3)

  def test_library_refuses_a_path_outside_the_library(self):
    response = self.go('GET', '/api/library', query={'path': '../..'})
    self.assertEqual(response.status, 400)
    self.assertIn('Not a path in the library', response.payload['message'])

  def test_library_missing_folder(self):
    response = self.go('GET', '/api/library', query={'path': 'nope'})
    self.assertEqual(response.status, 400)

  ###
  ### pools and loading
  ###

  def test_pools_starts_empty(self):
    response = self.go('GET', '/api/pools')
    self.assertEqual(response.payload['pools'], [])

  def test_load_sets_the_active_pool(self):
    response = self.load_a_text()

    self.assertEqual(response.status, 200)
    self.assertEqual(response.payload['data']['size'], 3)
    self.assertEqual(response.payload['pools'],
                     [{'name': 'words', 'size': 3, 'active': True,
                       'source': self.td.td.tf1_path}])

  def test_a_random_load_reports_its_source(self):
    response = self.go('POST', '/api/pools/random', body={'mode': 'flat'})
    source = response.payload['data']['source']
    self.assertEqual(response.payload['pools'][0]['source'], source)

  def test_load_needs_a_source(self):
    self.assertEqual(self.go('POST', '/api/pools/load').status, 400)
    self.assertEqual(self.go('POST', '/api/pools/load',
                             body={'source': 7}).status, 400)

  def test_load_refuses_an_escape(self):
    response = self.go('POST', '/api/pools/load',
                       body={'source': '../../etc/passwd'})
    self.assertEqual(response.status, 400)
    self.assertFalse(self.session.context)

  def test_random_flat(self):
    response = self.go('POST', '/api/pools/random', body={'mode': 'flat'})
    self.assertEqual(response.status, 200)
    self.assertIn('source', response.payload['data'])

  def test_random_walk(self):
    response = self.go('POST', '/api/pools/random', body={'mode': 'walk'})
    self.assertEqual(response.status, 200)

  def test_random_rejects_an_unknown_mode(self):
    response = self.go('POST', '/api/pools/random', body={'mode': 'sideways'})
    self.assertEqual(response.status, 400)

  def test_random_in_an_empty_folder(self):
    import os
    os.mkdir(os.path.join(self.td.root, 'empty'))
    response = self.go('POST', '/api/pools/random', body={'under': 'empty'})
    self.assertEqual(response.status, 400)

  ###
  ### drawing
  ###

  def test_draw(self):
    self.load_a_text()
    response = self.go('POST', '/api/draw', body={'count': 3})

    self.assertEqual(response.status, 200)
    self.assertEqual(len(response.payload['data']['drawn']), 3)

  def test_draw_without_a_pool(self):
    response = self.go('POST', '/api/draw', body={'count': 1})
    self.assertEqual(response.status, 400)
    self.assertIn('No words are loaded', response.payload['message'])

  def test_draw_count_is_capped(self):
    self.load_a_text()
    response = self.go('POST', '/api/draw', body={'count': 10_000})
    self.assertEqual(len(response.payload['data']['drawn']), 1000)

  def test_draw_rejects_nonsense_counts(self):
    self.load_a_text()
    for count in ['many', None, 0, -1]:
      with self.subTest(count=count):
        self.assertEqual(self.go('POST', '/api/draw',
                                 body={'count': count}).status, 400)

  ###
  ### the command language
  ###

  def test_command_runs_a_line(self):
    response = self.go('POST', '/api/command',
                       body={'line': f'load {self.td.td.tf1_path}'})
    self.assertEqual(response.status, 200)
    self.assertIn('words', self.session.context)

  def test_command_load_names_the_pool_it_loaded(self):
    # A load through a named route already recorded its source; one typed at
    # the command line used to leave the page naming the previous pool.
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf1_path})
    response = self.go('POST', '/api/command',
                       body={'line': f'load {self.td.td.tf4_path}'})
    self.assertEqual(response.status, 200)
    active = [p for p in response.payload['pools'] if p['active']][0]
    self.assertEqual(active['source'], self.td.td.tf4_path)

  def test_command_that_reports_no_source_leaves_the_name_alone(self):
    # `rare` and the set operations narrow a pool without changing which
    # text it came from, so they must not blank the label either.
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf1_path})
    self.go('POST', '/api/command', body={'line': 'dump'})
    pools = self.go('GET', '/api/pools').payload['pools']
    active = [p for p in pools if p['active']][0]
    self.assertEqual(active['source'], self.td.td.tf1_path)

  def test_command_refuses_quit(self):
    for line in ['quit', 'exit', 'q']:
      with self.subTest(line=line):
        response = self.go('POST', '/api/command', body={'line': line})
        self.assertEqual(response.status, 400)
        self.assertIn('no session to quit', response.payload['message'])

  def test_command_reports_an_unresolved_line(self):
    response = self.go('POST', '/api/command', body={'line': 'zzz'})
    self.assertEqual(response.status, 400)
    self.assertIn("don't understand", response.payload['message'])

  def test_command_asks_before_overwriting(self):
    self.load_a_text()
    self.go('POST', '/api/command', body={'line': 'al saved'})

    response = self.go('POST', '/api/command', body={'line': 'al saved'})

    self.assertEqual(response.status, 409)
    self.assertIn('Overwrite', response.payload['confirm'])

  def test_command_refuses_an_escape(self):
    response = self.go('POST', '/api/command', body={'line': 'ls ../..'})
    self.assertEqual(response.status, 400)

  ###
  ### misc
  ###

  def test_status_reports_the_cache(self):
    self.load_a_text()
    response = self.go('GET', '/api/status')
    self.assertEqual(response.status, 200)
    self.assertEqual(response.payload['cache']['files'], 1)

  def test_unknown_endpoint(self):
    self.assertEqual(self.go('GET', '/api/nope').status, 404)

  ###
  ### saving, forgetting and combining
  ###

  def test_save_names_the_active_pool(self):
    self.load_a_text()

    response = self.go('POST', '/api/pools/save', body={'name': 'kept'})

    self.assertEqual(response.status, 200)
    names = {p['name'] for p in response.payload['pools']}
    self.assertEqual(names, {'words', 'kept'})

  def test_save_records_where_the_pool_came_from(self):
    self.load_a_text()
    response = self.go('POST', '/api/pools/save', body={'name': 'kept'})
    saved = next(p for p in response.payload['pools'] if p['name'] == 'kept')
    self.assertEqual(saved['source'], self.td.td.tf1_path)

  def test_save_from_a_named_text(self):
    response = self.go('POST', '/api/pools/save',
                       body={'name': 'other', 'from': self.td.td.tf4_path})
    saved = next(p for p in response.payload['pools'] if p['name'] == 'other')
    self.assertEqual(saved['size'], 3)
    self.assertEqual(saved['source'], self.td.td.tf4_path)

  def test_save_needs_a_name(self):
    self.load_a_text()
    self.assertEqual(self.go('POST', '/api/pools/save').status, 400)
    self.assertEqual(self.go('POST', '/api/pools/save',
                             body={'name': ''}).status, 400)

  def test_save_over_a_name_asks_first(self):
    self.load_a_text()
    self.go('POST', '/api/pools/save', body={'name': 'kept'})
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/save', body={'name': 'kept'})

    self.assertEqual(response.status, 409)
    self.assertIn('Overwrite', response.payload['confirm'])
    self.assertCountEqual(self.session.context['kept'], ['a', 'b', 'c'])

  def test_save_with_force_replaces(self):
    self.load_a_text()
    self.go('POST', '/api/pools/save', body={'name': 'kept'})
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/save',
                       body={'name': 'kept', 'force': True})

    self.assertEqual(response.status, 200)
    self.assertNotIn('confirm', response.payload)
    self.assertCountEqual(self.session.context['kept'], ['one', 'two', 'three'])

  def test_forget_removes_a_pool(self):
    self.load_a_text()
    self.go('POST', '/api/pools/save', body={'name': 'kept'})

    response = self.go('DELETE', '/api/pools/kept')

    self.assertEqual(response.status, 200)
    self.assertEqual({p['name'] for p in response.payload['pools']}, {'words'})

  def test_forget_refuses_the_active_pool(self):
    self.load_a_text()
    response = self.go('DELETE', '/api/pools/words')
    self.assertEqual(response.status, 400)
    self.assertIn('words', self.session.context)

  def test_forget_an_unknown_pool(self):
    self.assertEqual(self.go('DELETE', '/api/pools/nope').status, 400)

  def test_combine_union(self):
    self.go('POST', '/api/pools/save',
            body={'name': 'a', 'from': self.td.td.tf1_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'b', 'from': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/op',
                       body={'op': 'union', 'a': 'a', 'b': 'b', 'out': 'both'})

    sizes = {p['name']: p['size'] for p in response.payload['pools']}
    self.assertEqual(sizes['both'], 6)

  def test_combine_difference_is_not_symmetric(self):
    self.go('POST', '/api/pools/save',
            body={'name': 'a', 'from': self.td.td.tf1_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'b', 'from': self.td.td.tf4_path})

    self.go('POST', '/api/pools/op',
            body={'op': 'difference', 'a': 'a', 'b': 'b', 'out': 'left'})
    response = self.go('POST', '/api/pools/op',
                       body={'op': 'difference', 'a': 'b', 'b': 'a',
                             'out': 'right'})

    sizes = {p['name']: p['size'] for p in response.payload['pools']}
    self.assertEqual((sizes['left'], sizes['right']), (3, 3))
    self.assertCountEqual(self.session.context['left'], ['a', 'b', 'c'])
    self.assertCountEqual(self.session.context['right'],
                          ['one', 'two', 'three'])

  def test_combine_without_an_out_name_replaces_the_first(self):
    self.go('POST', '/api/pools/save',
            body={'name': 'a', 'from': self.td.td.tf1_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'b', 'from': self.td.td.tf4_path})

    self.go('POST', '/api/pools/op',
            body={'op': 'union', 'a': 'a', 'b': 'b'})

    self.assertEqual(len(self.session.context['a']), 6)

  def test_combine_rejects_a_bad_operation(self):
    response = self.go('POST', '/api/pools/op',
                       body={'op': 'sideways', 'a': 'a', 'b': 'b'})
    self.assertEqual(response.status, 400)
    self.assertIn('union, difference or intersection',
                  response.payload['message'])

  def test_combine_needs_two_pools(self):
    for body in [{'op': 'union'}, {'op': 'union', 'a': 'a'},
                 {'op': 'union', 'b': 'b'}]:
      with self.subTest(body=body):
        self.assertEqual(self.go('POST', '/api/pools/op', body=body).status, 400)

  def test_combine_onto_an_existing_out_asks_first(self):
    self.go('POST', '/api/pools/save',
            body={'name': 'a', 'from': self.td.td.tf1_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'b', 'from': self.td.td.tf4_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'out', 'from': self.td.td.tf5_path})

    response = self.go('POST', '/api/pools/op',
                       body={'op': 'union', 'a': 'a', 'b': 'b', 'out': 'out'})

    self.assertEqual(response.status, 409)
    self.assertIn('Overwrite', response.payload['confirm'])
    self.assertCountEqual(self.session.context['out'], ['five'])

  def test_combine_onto_an_existing_out_with_force_replaces(self):
    self.go('POST', '/api/pools/save',
            body={'name': 'a', 'from': self.td.td.tf1_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'b', 'from': self.td.td.tf4_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'out', 'from': self.td.td.tf5_path})

    response = self.go('POST', '/api/pools/op',
                       body={'op': 'union', 'a': 'a', 'b': 'b', 'out': 'out',
                             'force': True})

    self.assertEqual(response.status, 200)
    self.assertNotIn('confirm', response.payload)
    self.assertEqual(len(self.session.context['out']), 6)

  def test_command_with_force_answers_the_question(self):
    self.load_a_text()
    self.go('POST', '/api/command', body={'line': 'al kept'})
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf4_path})

    asked = self.go('POST', '/api/command', body={'line': 'al kept'})
    self.assertEqual(asked.status, 409)

    forced = self.go('POST', '/api/command',
                     body={'line': 'al kept', 'force': True})
    self.assertEqual(forced.status, 200)
    self.assertCountEqual(self.session.context['kept'],
                          ['one', 'two', 'three'])

  def test_both_save_paths_record_the_same_source(self):
    self.load_a_text()

    self.go('POST', '/api/pools/save', body={'name': 'by_button'})
    self.go('POST', '/api/command', body={'line': 'al by_command'})
    response = self.go('POST', '/api/command',
                       body={'line': f'al from_file {self.td.td.tf4_path}'})

    sources = {p['name']: p['source'] for p in response.payload['pools']}
    self.assertEqual(sources['by_button'], self.td.td.tf1_path)
    self.assertEqual(sources['by_command'], self.td.td.tf1_path)
    self.assertEqual(sources['from_file'], self.td.td.tf4_path)

  def test_a_derived_pool_names_no_source(self):
    self.go('POST', '/api/pools/save',
            body={'name': 'a', 'from': self.td.td.tf1_path})
    self.go('POST', '/api/pools/save',
            body={'name': 'b', 'from': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/op',
                       body={'op': 'union', 'a': 'a', 'b': 'b', 'out': 'both'})

    sources = {p['name']: p['source'] for p in response.payload['pools']}
    self.assertIsNone(sources['both'])

  def test_save_refuses_a_name_the_terminal_could_not_use(self):
    self.load_a_text()
    for name in ['has space', 'a/b', 'load classics/x.txt']:
      with self.subTest(name=name):
        response = self.go('POST', '/api/pools/save', body={'name': name})
        self.assertEqual(response.status, 400)
        self.assertNotIn(name, self.session.context)

  ###
  ### writing a pool to disk
  ###

  def test_write_names_the_active_pool(self):
    self.load_a_text()

    response = self.go('POST', '/api/pools/write', body={'name': 'kept'})

    self.assertEqual(response.status, 200)
    self.assertIn('custom/kept.txt', response.payload['message'])
    self.assertEqual(response.payload['data']['size'], 3)
    self.assertCountEqual(self.fm.get_words('custom/kept.txt'), ['a', 'b', 'c'])

  def test_write_a_named_pool(self):
    self.load_a_text()
    self.go('POST', '/api/pools/save', body={'name': 'saved'})
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/write',
                       body={'name': 'kept', 'pool': 'saved'})

    self.assertEqual(response.status, 200)
    self.assertCountEqual(self.fm.get_words('custom/kept.txt'), ['a', 'b', 'c'])

  def test_write_needs_a_name(self):
    self.load_a_text()
    self.assertEqual(self.go('POST', '/api/pools/write').status, 400)
    self.assertEqual(self.go('POST', '/api/pools/write',
                             body={'name': ''}).status, 400)

  def test_write_without_an_active_pool_fails(self):
    response = self.go('POST', '/api/pools/write', body={'name': 'kept'})
    self.assertEqual(response.status, 400)

  def test_write_refuses_a_name_the_terminal_could_not_use(self):
    self.load_a_text()
    for name in ['has space', 'a/b', 'a.txt']:
      with self.subTest(name=name):
        response = self.go('POST', '/api/pools/write', body={'name': name})
        self.assertEqual(response.status, 400)

  def test_write_over_an_existing_file_asks_first(self):
    self.load_a_text()
    self.go('POST', '/api/pools/write', body={'name': 'kept'})
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/write', body={'name': 'kept'})

    self.assertEqual(response.status, 409)
    self.assertIn('Overwrite', response.payload['confirm'])
    self.assertCountEqual(self.fm.get_words('custom/kept.txt'), ['a', 'b', 'c'])

  def test_write_with_force_replaces_the_file_on_disk(self):
    self.load_a_text()
    self.go('POST', '/api/pools/write', body={'name': 'kept'})
    self.go('POST', '/api/pools/load', body={'source': self.td.td.tf4_path})

    response = self.go('POST', '/api/pools/write',
                       body={'name': 'kept', 'force': True})

    self.assertEqual(response.status, 200)
    self.assertNotIn('confirm', response.payload)
    self.assertIn('custom/kept.txt', response.payload['message'])
    self.assertCountEqual(self.fm.get_words('custom/kept.txt'),
                          ['one', 'two', 'three'])

  def test_write_does_not_change_the_in_memory_pools(self):
    # Writing to disk is not the same as saving an alias: the pool list
    # over the wire should be unchanged by it.
    self.load_a_text()
    before = self.go('GET', '/api/pools').payload['pools']

    self.go('POST', '/api/pools/write', body={'name': 'kept'})

    after = self.go('GET', '/api/pools').payload['pools']
    self.assertEqual(before, after)
