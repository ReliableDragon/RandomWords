import http.client
import json
import os
import re
import tempfile
import threading
import unittest

from fake_directories import FakeDirectories
import web_server
from web_server import make_server


class ServerTest(unittest.TestCase):

  def setUp(self):
    self.td = FakeDirectories()
    self.td.__enter__()
    self.server = make_server(port=0, root=self.td.root)
    self.port = self.server.server_port
    # A short poll interval: the default half second is paid by every test
    # in shutdown, and there are a lot of them.
    self.thread = threading.Thread(
        target=self.server.serve_forever, kwargs={'poll_interval': 0.01},
        daemon=True)
    self.thread.start()

  def tearDown(self):
    self.server.shutdown()
    self.server.server_close()
    self.thread.join(timeout=5)
    self.td.__exit__(None, None, None)

  # Sends a request with exactly the headers given, so the checks can be
  # driven with the headers a browser would really send.
  def send(self, method, path, body=None, headers=None, host=None, port=None):
    port = self.port if port is None else port
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
      conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
      conn.putheader('Host', host if host is not None else f'127.0.0.1:{port}')
      payload = b''
      if body is not None:
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        conn.putheader('Content-Length', str(len(payload)))
      for name, value in (headers or {}).items():
        conn.putheader(name, value)
      conn.endheaders()
      if payload:
        conn.send(payload)
      response = conn.getresponse()
      raw = response.read()
      try:
        return response.status, json.loads(raw)
      except ValueError:
        return response.status, raw
    finally:
      conn.close()

  def post(self, path, body, headers=None, host=None, port=None):
    merged = {'Content-Type': 'application/json'}
    merged.update(headers or {})
    return self.send('POST', path, body=body, headers=merged, host=host, port=port)

  def start_additional_server(self, vault=None):
    server = make_server(port=0, root=self.td.root, vault=vault)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
    thread.start()
    def stop():
      server.shutdown()
      server.server_close()
      thread.join(timeout=5)
    self.addCleanup(stop)
    return server

  ###
  ### the origin table: loopback is not a trust boundary on its own
  ###

  def test_a_normal_request_is_served(self):
    status, payload = self.send('GET', '/api/pools')
    self.assertEqual(status, 200)
    self.assertTrue(payload['ok'])

  def test_localhost_host_header_is_served(self):
    status, _ = self.send('GET', '/api/pools', host=f'localhost:{self.port}')
    self.assertEqual(status, 200)

  def test_foreign_host_header_is_refused(self):
    # This is the DNS rebinding check.
    status, payload = self.send('GET', '/api/pools', host='evil.example.com')
    self.assertEqual(status, 403)
    self.assertFalse(payload['ok'])

  def test_right_host_wrong_port_is_refused(self):
    status, _ = self.send('GET', '/api/pools', host='127.0.0.1:1')
    self.assertEqual(status, 403)

  def test_post_without_a_json_content_type_is_refused(self):
    status, _ = self.send('POST', '/api/draw', body={'count': 1},
                          headers={'Content-Type': 'text/plain'})
    self.assertEqual(status, 403)

  def test_post_with_a_form_content_type_is_refused(self):
    # The type a cross-origin form can send without a preflight.
    status, _ = self.send(
        'POST', '/api/draw', body={'count': 1},
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    self.assertEqual(status, 403)

  def test_foreign_origin_is_refused(self):
    status, _ = self.post('/api/draw', {'count': 1},
                          headers={'Origin': 'https://evil.example.com'})
    self.assertEqual(status, 403)

  def test_matching_origin_is_served(self):
    status, _ = self.post('/api/draw', {'count': 1},
                          headers={'Origin': f'http://127.0.0.1:{self.port}'})
    # 400 because no pool is loaded; the point is that it got past the checks.
    self.assertEqual(status, 400)

  def test_absent_origin_is_served(self):
    status, _ = self.post('/api/pools/load', {'source': self.td.tf1_path})
    self.assertEqual(status, 200)

  ###
  ### bodies
  ###

  def test_body_over_the_cap_is_refused(self):
    status, payload = self.post('/api/draw', b'{"count":1}' + b' ' * (70 * 1024))
    self.assertEqual(status, 400)
    self.assertIn('too large', payload['message'])

  def test_world_nearby_accepts_body_above_regular_post_cap(self):
    with tempfile.TemporaryDirectory() as vault_dir:
      server = self.start_additional_server(vault=vault_dir)
      body = {'text': 'A' * (70 * 1024), 'path': 'Draft.md', 'client_revision': 1}
      status, payload = self.post('/api/world/nearby', body, port=server.server_port)
      self.assertEqual(status, 200, payload)
      self.assertTrue(payload['ok'])

  def test_malformed_json_is_refused(self):
    status, payload = self.post('/api/draw', b'{not json')
    self.assertEqual(status, 400)
    self.assertIn('not JSON', payload['message'])

  def test_a_json_array_body_is_refused(self):
    status, payload = self.post('/api/draw', b'[1,2,3]')
    self.assertEqual(status, 400)
    self.assertIn('JSON object', payload['message'])

  ###
  ### routing and static files
  ###

  def test_the_page_is_served(self):
    status, raw = self.send('GET', '/')
    self.assertEqual(status, 200)
    self.assertIn(b'<', raw)

  def test_walkthrough_is_served_without_a_vault(self):
    status, raw = self.send('GET', '/walkthrough')
    self.assertEqual(status, 200)
    self.assertIn(b'Worldbuilding walkthrough', raw)
    self.assertIn(b'python3 serve.py --vault', raw)
    self.assertIn(b'id="open-your-vault"', raw)
    self.assertNotIn(b'href="/world">Open desk', raw)

  def test_embedded_generator_is_the_index_page_and_may_be_framed(self):
    # The world desk loads /?embed=1 in a same-origin iframe, so the page must
    # be served as usual and nothing may forbid framing it.
    conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
    try:
      conn.request('GET', '/?embed=1')
      response = conn.getresponse()
      raw = response.read()
      names = {name.lower() for name, _ in response.getheaders()}
    finally:
      conn.close()
    self.assertEqual(response.status, 200)
    self.assertIn(b'<script src="/embed.js"></script>', raw)
    self.assertIn(b'id="drawBtn"', raw)
    self.assertNotIn('x-frame-options', names)
    self.assertNotIn('content-security-policy', names)

  def test_embed_script_is_served_as_a_file(self):
    # Embed detection lives in a file, not an inline script, so a hosted
    # Content-Security-Policy can forbid inline scripts.
    conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
    try:
      conn.request('GET', '/embed.js')
      response = conn.getresponse()
      raw = response.read()
    finally:
      conn.close()
    self.assertEqual(response.status, 200)
    self.assertIn(b'data-embed', raw)

  def test_unknown_static_path_is_not_found(self):
    status, payload = self.send('GET', '/secrets.txt')
    self.assertEqual(status, 404)

  def test_world_routes_are_opt_in(self):
    status, _ = self.send('GET', '/world')
    self.assertEqual(status, 404)
    status, _ = self.send('GET', '/api/world/tree')
    self.assertEqual(status, 404)

  def test_configured_vault_serves_world_page_and_tree_api(self):
    with tempfile.TemporaryDirectory() as vault_dir:
      with open(os.path.join(vault_dir, 'A note.md'), 'w', encoding='utf-8') as f:
        f.write('A note body.')
      server = self.start_additional_server(vault=vault_dir)
      status, raw = self.send('GET', '/world', port=server.server_port)
      self.assertEqual(status, 200)
      self.assertIn(b'<!doctype html', raw.lower())
      status, guide = self.send('GET', '/walkthrough', port=server.server_port)
      self.assertEqual(status, 200)
      self.assertIn(b'href="/world">Open desk', guide)
      status, payload = self.send('GET', '/api/world/tree', port=server.server_port)
      self.assertEqual(status, 200, payload)
      self.assertTrue(payload['ok'])
      self.assertEqual([row['path'] for row in payload['data']['entries']], ['A note.md'])

  ###
  ### the world desk's ES modules
  ###

  def fetch_with_headers(self, path, port):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
      conn.request('GET', path, headers={'Host': f'127.0.0.1:{port}'})
      response = conn.getresponse()
      raw = response.read()
      return response.status, response.getheader('Content-Type'), raw
    finally:
      conn.close()

  def test_module_routes_only_list_plain_lowercase_javascript_files(self):
    with tempfile.TemporaryDirectory() as directory:
      for name in ['main.js', 'entry_header.js', 'Main.js', 'a-b.js', 'x1.js',
                   '.hidden.js', 'notes.txt', 'main.js.map', 'main.jsx',
                   'v2.min.js', 'A1.js']:
        with open(os.path.join(directory, name), 'w') as f:
          f.write('export {};')
      os.mkdir(os.path.join(directory, 'folder.js'))
      routes = web_server.module_routes(directory)
    # Digits are fine; dots, dashes and capitals are not.
    self.assertEqual(sorted(routes),
                     ['/world/entry_header.js', '/world/main.js', '/world/x1.js'])
    self.assertEqual(routes['/world/main.js'],
                     ('world/main.js', 'text/javascript; charset=utf-8'))

  def test_module_routes_tolerate_a_missing_directory(self):
    self.assertEqual(web_server.module_routes('/nonexistent-module-dir'), {})

  def test_the_shipped_modules_are_all_in_the_table(self):
    shipped = [n for n in os.listdir(web_server.MODULE_DIR) if n.endswith('.js')]
    self.assertIn('main.js', shipped)
    for name in shipped:
      with self.subTest(name=name):
        self.assertRegex(name, r'^[a-z0-9_]+\.js$')
        self.assertIn(f'/world/{name}', web_server.STATIC)

  def test_every_module_import_is_a_served_module(self):
    for name in os.listdir(web_server.MODULE_DIR):
      with open(os.path.join(web_server.MODULE_DIR, name), encoding='utf-8') as f:
        source = f.read()
      for target in re.findall(r"from '\./([^']+)'", source):
        with self.subTest(module=name, imports=target):
          self.assertIn(f'/world/{target}', web_server.STATIC)

  def test_world_page_loads_the_module_entry_point_after_the_atlas(self):
    with open(os.path.join(web_server.STATIC_DIR, 'world.html'), encoding='utf-8') as f:
      page = f.read()
    self.assertIn('<script type="module" src="/world/main.js"></script>', page)
    self.assertLess(page.index('/world_atlas.js'), page.index('/world/main.js'))
    self.assertNotIn('/world.js', page)
    self.assertNotIn('/world_map.js', page)

  def test_world_modules_are_served_as_javascript_with_a_vault(self):
    with tempfile.TemporaryDirectory() as vault_dir:
      server = self.start_additional_server(vault=vault_dir)
      for name in ['main.js', 'api.js', 'storage.js', 'create.js', 'map.js']:
        with self.subTest(name=name):
          status, content_type, raw = self.fetch_with_headers(
              f'/world/{name}', server.server_port)
          self.assertEqual(status, 200)
          self.assertEqual(content_type, 'text/javascript; charset=utf-8')
          self.assertTrue(b'import ' in raw or b'export ' in raw)
      status, content_type, _ = self.fetch_with_headers(
          '/world_atlas.js', server.server_port)
      self.assertEqual((status, content_type),
                       (200, 'text/javascript; charset=utf-8'))

  def test_world_modules_need_a_vault(self):
    status, _, _ = self.fetch_with_headers('/world/main.js', self.port)
    self.assertEqual(status, 404)

  def test_the_old_world_scripts_are_gone(self):
    with tempfile.TemporaryDirectory() as vault_dir:
      server = self.start_additional_server(vault=vault_dir)
      for path in ['/world.js', '/world_map.js']:
        with self.subTest(path=path):
          status, _, _ = self.fetch_with_headers(path, server.server_port)
          self.assertEqual(status, 404)

  def test_odd_module_names_are_not_served(self):
    with tempfile.TemporaryDirectory() as vault_dir:
      server = self.start_additional_server(vault=vault_dir)
      for path in ['/world/Main.js', '/world/../web_server.py', '/world/%2e%2e/web_server.py',
                   '/world/..%2fweb_server.py', '/world/nothing.js', '/world/main.js/',
                   '/world/main.js%00.txt', '/world/', '/world//main.js']:
        with self.subTest(path=path):
          status, _, raw = self.fetch_with_headers(path, server.server_port)
          self.assertEqual(status, 404)
          self.assertNotIn(b'import ', raw)

  def test_a_traversal_in_the_url_finds_nothing(self):
    for path in ['/../file_manager.py', '/static/../serve.py', '/app.js/../../serve.py']:
      with self.subTest(path=path):
        status, _ = self.send('GET', path)
        self.assertEqual(status, 404)

  def test_end_to_end_load_and_draw(self):
    status, payload = self.post('/api/pools/load', {'source': self.td.tf1_path})
    self.assertEqual(status, 200)

    status, payload = self.post('/api/draw', {'count': 2})
    self.assertEqual(status, 200)
    self.assertEqual(len(payload['data']['drawn']), 2)
    for word in payload['data']['drawn']:
      self.assertIn(word, ['a', 'b', 'c'])

  def test_delete_over_http(self):
    self.post('/api/pools/load', {'source': self.td.tf1_path})
    self.post('/api/pools/save', {'name': 'kept'})

    status, payload = self.send('DELETE', '/api/pools/kept')

    self.assertEqual(status, 200)
    self.assertEqual({p['name'] for p in payload['pools']}, {'words'})

  def test_delete_from_a_foreign_origin_is_refused(self):
    self.post('/api/pools/load', {'source': self.td.tf1_path})
    self.post('/api/pools/save', {'name': 'kept'})

    status, _ = self.send('DELETE', '/api/pools/kept',
                          headers={'Origin': 'https://evil.example.com'})

    self.assertEqual(status, 403)
    status, payload = self.send('GET', '/api/pools')
    self.assertIn('kept', {p['name'] for p in payload['pools']})

  def test_a_percent_encoded_pool_name_is_decoded(self):
    self.post('/api/pools/load', {'source': self.td.tf1_path})
    self.post('/api/command', {'line': 'al a_b'})

    status, payload = self.send('DELETE', '/api/pools/a%5Fb')

    self.assertEqual(status, 200)
    self.assertEqual({p['name'] for p in payload['pools']}, {'words'})

  def test_concurrent_requests(self):
    self.post('/api/pools/load', {'source': self.td.tf1_path})
    results = []

    def draw():
      results.append(self.post('/api/draw', {'count': 1})[0])

    threads = [threading.Thread(target=draw) for _ in range(20)]
    for t in threads:
      t.start()
    for t in threads:
      t.join(timeout=10)

    self.assertEqual(results, [200] * 20)
