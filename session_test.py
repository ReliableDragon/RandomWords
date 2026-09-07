import threading
import unittest

from fake_file_manager import FakeFileManager
from session import Session, SessionStore


class SessionTest(unittest.TestCase):

  def test_run_applies_updates(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)

      result = session.run('load', [tfm.td.tf1_path])

      self.assertTrue(result.ok)
      self.assertCountEqual(session.context['words'], ['a', 'b', 'c'])

  def test_a_failure_changes_nothing(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)
      session.run('load', [tfm.td.tf1_path])

      result = session.run('load', ['nope.txt'])

      self.assertFalse(result.ok)
      self.assertCountEqual(session.context['words'], ['a', 'b', 'c'])

  def test_run_line_uses_the_command_language(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)
      result = session.run_line(f'load {tfm.td.tf1_path}')
      self.assertTrue(result.ok)
      self.assertIn('words', session.context)

  def test_run_line_reports_an_unresolved_line(self):
    with FakeFileManager() as tfm:
      result = Session(tfm).run_line('zzz not a command')
      self.assertFalse(result.ok)
      self.assertEqual(result.message, "I'm sorry, I don't understand.")

  def test_confirmation_is_withheld_until_applied(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)
      session.run('load', [tfm.td.tf1_path])
      session.run('alias_load', ['saved'])

      result = session.run('alias_load', ['saved', tfm.td.tf4_path])

      self.assertTrue(result.confirm)
      self.assertCountEqual(session.context['saved'], ['a', 'b', 'c'])

      session.apply(result)
      self.assertCountEqual(session.context['saved'], ['one', 'two', 'three'])

  def test_pools_reports_sizes_not_words(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)
      session.run('load', [tfm.td.tf1_path])

      pools = session.pools()

      self.assertEqual(pools, [{'name': 'words', 'size': 3, 'active': True,
                                'source': None}])

  def test_pools_report_where_they_came_from(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)
      session.run('load', [tfm.td.tf1_path])
      session.note_source('words', tfm.td.tf1_path)

      self.assertEqual(session.pools()[0]['source'], tfm.td.tf1_path)

  def test_store_hands_everyone_the_same_session(self):
    with FakeFileManager() as tfm:
      store = SessionStore(tfm)
      self.assertIs(store.for_request(), store.for_request())

  def test_concurrent_saves_all_survive(self):
    with FakeFileManager() as tfm:
      session = Session(tfm)
      session.run('load', [tfm.td.tf1_path])
      errors = []

      def save(n):
        try:
          session.run('alias_load', [f'pool{n}'])
        except Exception as e:   # pragma: no cover - only on a real failure
          errors.append(e)

      threads = [threading.Thread(target=save, args=(n,)) for n in range(20)]
      for t in threads:
        t.start()
      for t in threads:
        t.join(timeout=10)

      self.assertEqual(errors, [])
      # The thing to lose here is an update, not interleaved output.
      for n in range(20):
        self.assertCountEqual(session.context[f'pool{n}'], ['a', 'b', 'c'])
