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
