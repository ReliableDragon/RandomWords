import json
import logging
import os

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import web_routes

from session import SessionStore
from word_cache import CachingFileManager
from word_index import WordIndex

logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# Served from a fixed table rather than by joining the URL onto a directory,
# so there is no second path resolver to get wrong.
STATIC = {
  '/': ('index.html', 'text/html; charset=utf-8'),
  '/index.html': ('index.html', 'text/html; charset=utf-8'),
  '/app.css': ('app.css', 'text/css; charset=utf-8'),
  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
}

MAX_BODY = 64 * 1024
LOOPBACK_HOSTS = ('localhost', '127.0.0.1', '[::1]', '::1')


class Handler(BaseHTTPRequestHandler):

  protocol_version = 'HTTP/1.1'
  server_version = 'RandomWords'

  def do_GET(self):
    self.handle_request('GET')

  def do_POST(self):
    self.handle_request('POST')

  def do_DELETE(self):
    self.handle_request('DELETE')

  def handle_request(self, method):
    refusal = self.check_caller(method)
    if refusal:
      # Deliberately terse: telling a caller which check it failed helps
      # nobody who is allowed to be here.
      self.refuse(403, refusal)
      return

    parsed = urlparse(self.path)
    if method == 'GET' and parsed.path in STATIC:
      self.send_static(parsed.path)
      return

    body, problem = self.read_body(method)
    if problem:
      self.refuse(400, problem)
      return

    request = web_routes.Request(
        method=method,
        path=unquote(parsed.path),
        query={k: v[0] for k, v in parse_qs(parsed.query).items()},
        body=body,
        session=self.server.sessions.for_request(self.headers),
        fm=self.server.fm)

    try:
      response = web_routes.dispatch(request)
    except Exception:
      logger.exception('unhandled error serving %s %s', method, parsed.path)
      self.send_json(500, {'ok': False, 'message': 'Something went wrong here.'})
      return

    self.send_json(response.status, response.payload)

  # Binding to loopback keeps the network out. It does not keep out a web
  # page: any tab in the same browser can post to a loopback server, and DNS
  # rebinding lets a page the attacker controls read the replies too. These
  # three checks are what actually close that.
  #
  # Returns: a refusal message, or None to continue.
  def check_caller(self, method):
    host = (self.headers.get('Host') or '').strip()
    name = host.rsplit(':', 1)[0] if ':' in host and not host.endswith(']') else host
    port = host.rsplit(':', 1)[1] if ':' in host and not host.endswith(']') else ''
    if name not in LOOPBACK_HOSTS:
      return 'Not served to that host.'
    if port and port != str(self.server.server_port):
      return 'Not served to that host.'

    origin = self.headers.get('Origin')
    if origin is not None and origin not in self.allowed_origins():
      return 'Not served to that origin.'

    if method == 'POST':
      # A cross-origin POST with this content type needs a preflight this
      # server never answers, so the body never arrives.
      content_type = (self.headers.get('Content-Type') or '').split(';')[0].strip()
      if content_type != 'application/json':
        return 'Send application/json.'

    return None

  def allowed_origins(self):
    port = self.server.server_port
    return {f'http://{host}:{port}' for host in ('localhost', '127.0.0.1', '[::1]')}

  def read_body(self, method):
    if method != 'POST':
      return {}, None

    try:
      length = int(self.headers.get('Content-Length') or 0)
    except ValueError:
      return {}, 'Send a Content-Length.'
    if length > MAX_BODY:
      return {}, 'That request is too large.'
    if length == 0:
      return {}, None

    raw = self.rfile.read(length)
    try:
      body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
      return {}, 'That request body is not JSON.'
    if not isinstance(body, dict):
      return {}, 'That request body is not a JSON object.'
    return body, None

  # Answers without reading the request body, so the connection has to close
  # rather than leave an unread body in front of the next request.
  def refuse(self, status, message):
    self.close_connection = True
    self.send_json(status, {'ok': False, 'message': message})

  def send_static(self, url_path):
    filename, content_type = STATIC[url_path]
    try:
      with open(os.path.join(STATIC_DIR, filename), 'rb') as f:
        payload = f.read()
    except OSError:
      self.send_json(404, {'ok': False, 'message': 'Not found.'})
      return
    self.send_bytes(200, payload, content_type)

  def send_json(self, status, payload):
    self.send_bytes(status, json.dumps(payload).encode('utf-8'),
                    'application/json; charset=utf-8')

  def send_bytes(self, status, payload, content_type):
    self.send_response(status)
    self.send_header('Content-Type', content_type)
    self.send_header('Content-Length', str(len(payload)))
    # Nothing here is for anyone else to embed or sniff.
    self.send_header('X-Content-Type-Options', 'nosniff')
    self.send_header('Cache-Control', 'no-store')
    if self.close_connection:
      self.send_header('Connection', 'close')
    self.end_headers()
    self.wfile.write(payload)

  def log_message(self, fmt, *args):
    logger.info('%s %s', self.address_string(), fmt % args)


def make_server(port=0, root=None, host='127.0.0.1', index=None):
  fm = CachingFileManager() if root is None else CachingFileManager(root)
  index = WordIndex(fm) if index is None else index
  server = ThreadingHTTPServer((host, port), Handler)
  server.fm = fm
  server.index = index
  server.sessions = SessionStore(fm, index)
  server.daemon_threads = True
  return server
