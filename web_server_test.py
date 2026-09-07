import http.client
import json
import threading
import unittest

from fake_directories import FakeDirectories
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
  def send(self, method, path, body=None, headers=None, host=None):
    conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
    try:
      conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
      conn.putheader('Host', host if host is not None else f'127.0.0.1:{self.port}')
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

  def post(self, path, body, headers=None, host=None):
    merged = {'Content-Type': 'application/json'}
    merged.update(headers or {})
    return self.send('POST', path, body=body, headers=merged, host=host)

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

  def test_unknown_static_path_is_not_found(self):
    status, payload = self.send('GET', '/secrets.txt')
    self.assertEqual(status, 404)

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
