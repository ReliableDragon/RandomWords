import unittest

from fake_file_manager import FakeFileManager
from parser import UNKNOWN_COMMAND
from parser_test import DOCUMENTED_SYNTAXES
from session import Session
from web_routes import Request, dispatch
from word_cache import CachingFileManager

QUIT_SPELLINGS = {'quit', 'exit', 'q'}


# The check that stops the web layer from quietly losing a command. Every
# syntax the terminal documents is driven through the one endpoint that
# accepts the command language, using the same table the parser test pins.
class WebParityTest(unittest.TestCase):

  def setUp(self):
    self.td = FakeFileManager()
    self.td.__enter__()
    self.fm = CachingFileManager(self.td.root)
    self.session = Session(self.fm)

  def tearDown(self):
    self.td.__exit__(None, None, None)

  def run_line(self, line, force=False):
    body = {'line': line}
    if force:
      body['force'] = True
    return dispatch(Request('POST', '/api/command', {}, body,
                            session=self.session, fm=self.fm))

  def test_every_documented_syntax_is_understood(self):
    for line, command in DOCUMENTED_SYNTAXES:
      with self.subTest(line=line, command=command):
        response = self.run_line(line)

        # Understood is the claim, not successful: most of these name pools
        # and texts that do not exist in a bare session, and failing with a
        # real message is the right answer for those.
        self.assertNotEqual(response.payload.get('message'), UNKNOWN_COMMAND,
                            f'{line!r} was not recognised over HTTP')
        self.assertIn(response.status, (200, 400, 409))

  def test_quit_is_refused_rather_than_run(self):
    for line, command in DOCUMENTED_SYNTAXES:
      if command != 'quit':
        continue
      with self.subTest(line=line):
        self.assertIn(line.strip().lower(), QUIT_SPELLINGS)
        response = self.run_line(line)
        self.assertEqual(response.status, 400)
        self.assertIn('no session to quit', response.payload['message'])

  def test_every_command_in_the_table_is_covered(self):
    from command_list import CommandList
    registered = {cmd.name for cmd in CommandList(self.fm).cmd_list()}
    covered = {command for _, command in DOCUMENTED_SYNTAXES}
    self.assertEqual(registered - covered, set(),
                     'a registered command has no documented syntax')

  # A realistic session, end to end, entirely through the command language.
  def test_a_whole_session_over_http(self):
    tf1 = self.td.td.tf1_path        # a b c
    tf4 = self.td.td.tf4_path        # one two three

    self.assertEqual(self.run_line(f'load {tf1}').status, 200)
    self.assertEqual(self.run_line('al first').status, 200)
    self.assertEqual(self.run_line(f'load {tf4}').status, 200)
    self.assertEqual(self.run_line('al second').status, 200)

    response = self.run_line('c first second both')
    self.assertEqual(response.status, 200)
    sizes = {p['name']: p['size'] for p in response.payload['pools']}
    self.assertEqual(sizes['both'], 6)

    response = self.run_line('d both first only_second')
    self.assertEqual({p['name']: p['size']
                      for p in response.payload['pools']}['only_second'], 3)

    response = self.run_line('i first second shared')
    self.assertEqual({p['name']: p['size']
                      for p in response.payload['pools']}['shared'], 0)

    response = self.run_line('rm shared')
    self.assertNotIn('shared', {p['name'] for p in response.payload['pools']})

    response = self.run_line('gaw first second')
    self.assertEqual(response.status, 200)
    self.assertEqual(len(response.payload['data']['drawn']), 2)

  def test_the_overwrite_question_survives_the_round_trip(self):
    self.run_line(f'load {self.td.td.tf1_path}')
    self.run_line('al saved')

    asked = self.run_line('al saved')
    self.assertEqual(asked.status, 409)
    self.assertIn('Overwrite', asked.payload['confirm'])
    # Declining is simply not repeating the request.
    self.assertCountEqual(self.session.context['saved'], ['a', 'b', 'c'])

    self.run_line(f'load {self.td.td.tf4_path}')
    forced = self.run_line('al saved', force=True)
    self.assertEqual(forced.status, 200)
    self.assertCountEqual(self.session.context['saved'], ['one', 'two', 'three'])
