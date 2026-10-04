import hashlib
import json
import os
import tempfile
import threading
import unittest

from file_manager import FileManager
from vault import VaultManager
from vault_index import VaultIndex
from web_routes import Request
import world_triage
from world_routes import dispatch
from world_triage import TriageStore, default_base_dir, world_id


class TriageStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = os.path.join(self.temp.name, "worlds", "abc")
        self.store = TriageStore(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_file_is_empty_and_reading_creates_nothing(self):
        self.assertEqual(self.store.dismissed(), [])
        self.assertEqual(self.store.keys("name"), frozenset())
        self.assertFalse(os.path.exists(self.directory))

    def test_dismiss_restore_round_trip_persists_across_instances(self):
        self.assertTrue(self.store.dismiss("mention", "A.md|B.md"))
        self.assertFalse(self.store.dismiss("mention", "A.md|B.md"))
        self.assertTrue(self.store.dismiss("drift", "batar's→battar's"))
        again = TriageStore(self.directory)
        self.assertEqual([(r["kind"], r["key"]) for r in again.dismissed()],
                         [("drift", "batar's→battar's"), ("mention", "A.md|B.md")])
        self.assertEqual(again.keys("mention"), frozenset({"A.md|B.md"}))
        self.assertTrue(again.restore("mention", "A.md|B.md"))
        self.assertFalse(again.restore("mention", "A.md|B.md"))
        self.assertEqual(again.keys("mention"), frozenset())
        self.assertTrue(all(row["at"] for row in again.dismissed()))

    def test_name_and_word_keys_are_normalised_but_paths_are_not(self):
        self.store.dismiss("name", "Fate FOULERS")
        self.store.dismiss("word", "Café")
        self.store.dismiss("mention", "A/Case.md|B.md")
        self.assertEqual(self.store.keys("name"), frozenset({"fate foulers"}))
        self.assertEqual(self.store.keys("word"), frozenset({"café"}))
        self.assertEqual(self.store.keys("mention"), frozenset({"A/Case.md|B.md"}))
        self.assertTrue(self.store.restore("name", "fate foulers"))

    def test_write_is_atomic_and_leaves_no_temporary_files(self):
        for number in range(5):
            self.store.dismiss("word", f"word{number}")
        self.assertEqual(os.listdir(self.directory), ["triage.json"])
        with open(self.store.path, encoding="utf-8") as source:
            document = json.load(source)
        self.assertEqual(document["version"], 1)
        self.assertEqual(len(document["dismissed"]), 5)
        if os.name == "posix":
            self.assertEqual(os.stat(self.directory).st_mode & 0o077, 0)

    def test_failed_write_keeps_the_previous_file(self):
        self.store.dismiss("word", "kept")
        original = os.replace

        def broken(*_args):
            raise OSError("disk full")
        os.replace = broken
        try:
            with self.assertRaises(OSError):
                self.store.dismiss("word", "lost")
        finally:
            os.replace = original
        self.assertEqual(self.store.keys("word"), frozenset({"kept"}))
        self.assertEqual(os.listdir(self.directory), ["triage.json"])

    def test_corrupt_file_reads_as_empty_and_a_copy_is_kept(self):
        os.makedirs(self.directory)
        with open(self.store.path, "wb") as output:
            output.write(b"{not json")
        self.assertEqual(self.store.dismissed(), [])
        self.assertEqual(self.store.dismissed(), [])
        with open(self.store.path + ".corrupt", "rb") as copy:
            self.assertEqual(copy.read(), b"{not json")
        # The next write replaces the unreadable file, but the copy remains.
        self.store.dismiss("name", "x")
        self.assertEqual(self.store.keys("name"), frozenset({"x"}))
        with open(self.store.path + ".corrupt", "rb") as copy:
            self.assertEqual(copy.read(), b"{not json")

    def test_wrong_shapes_are_treated_as_corrupt(self):
        os.makedirs(self.directory)
        for content in (b"[]", b'{"version": 1, "dismissed": "x"}',
                        b'{"version": 1, "dismissed": [{"kind": "bogus", "key": "x"}]}',
                        b'{"version": 9, "dismissed": []}', b"\xff\xfe"):
            with open(self.store.path, "wb") as output:
                output.write(content)
            self.assertEqual(self.store.dismissed(), [], content)
        self.assertTrue(os.path.exists(self.store.path + ".corrupt"))

    def test_different_corrupt_contents_get_separate_copies(self):
        os.makedirs(self.directory)
        for content in (b"one", b"two"):
            with open(self.store.path, "wb") as output:
                output.write(content)
            self.store.dismissed()
        copies = sorted(name for name in os.listdir(self.directory) if ".corrupt" in name)
        self.assertEqual(copies, ["triage.json.corrupt", "triage.json.corrupt.1"])

    def test_concurrent_dismissals_are_all_kept(self):
        def work(start):
            store = TriageStore(self.directory)
            for number in range(start, start + 10):
                store.dismiss("word", f"w{number:03d}")
        threads = [threading.Thread(target=work, args=(n * 10,)) for n in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(self.store.keys("word")), 60)

    def test_validate(self):
        self.assertIsNone(world_triage.validate("name", "Fate Foulers"))
        for kind, key in (("other", "x"), (None, "x"), ("name", ""), ("name", "  "),
                          ("name", 5), ("name", None), ("name", "x" * 1001)):
            self.assertIsNotNone(world_triage.validate(kind, key), (kind, key))
        self.assertIsNone(world_triage.validate("name", "x" * 1000))

    def test_world_id_is_first_sixteen_hex_of_the_real_path_hash(self):
        root = os.path.realpath(self.temp.name)
        self.assertEqual(world_id(self.temp.name),
                         hashlib.sha256(root.encode("utf-8")).hexdigest()[:16])
        self.assertEqual(len(world_id(self.temp.name)), 16)
        link = os.path.join(self.temp.name, "link")
        os.symlink(self.temp.name, link)
        self.assertEqual(world_id(link), world_id(self.temp.name))

    def test_default_base_is_outside_the_vault_under_the_home_directory(self):
        self.assertEqual(default_base_dir(),
                         os.path.join(os.path.expanduser("~"), ".randomwords", "worlds"))

    def test_store_for_uses_injected_base_and_world_id(self):
        world_triage.set_base_dir(self.temp.name)
        try:
            store = world_triage.store_for("/some/vault")
            self.assertEqual(store.path, os.path.join(
                self.temp.name, world_id("/some/vault"), "triage.json"))
            self.assertIs(store, world_triage.store_for("/some/vault"))
        finally:
            world_triage.set_base_dir(None)


class TriageRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.temp.name, "vault")
        self.private = os.path.join(self.temp.name, "private")
        os.makedirs(self.root)
        world_triage.set_base_dir(self.private)
        self.vault = VaultManager(self.root, os.path.join(self.temp.name, "recovery"))
        self.fm = FileManager()

    def tearDown(self):
        world_triage.set_base_dir(None)
        self.temp.cleanup()

    def note(self, path, text=""):
        full = os.path.join(self.root, *path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as output:
            output.write(text)

    def request(self, method, path, query=None, body=None, index=None):
        return Request(method, path, query or {}, body or {}, vault=self.vault,
                       world_index=index, fm=self.fm)

    def triage(self, action, kind, key):
        return dispatch(self.request("POST", "/api/world/triage",
                                     body={"action": action, "kind": kind, "key": key}))

    def fixture(self):
        self.note("Creatures/Aitrip.md", "A drifting seed.")
        self.note("Creatures/Helay.md",
                  "Helay meets an Aitrip while the Fate Foulers watch. Alzarati songs. "
                  "Alzarati songs again. Alzarati once more.")
        self.note("Creatures/Examainour.md",
                  "Examainour keeps an Aitrip. The Fate Foulers return. Alzerati once. "
                  "Alzerati twice. Alzarati thrice.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        return index

    def health(self, index):
        response = dispatch(self.request("GET", "/api/world/health", index=index))
        self.assertEqual(response.status, 200)
        return response.payload["data"]

    def test_get_and_post_validate_and_list(self):
        empty = dispatch(self.request("GET", "/api/world/triage"))
        self.assertEqual(empty.status, 200)
        self.assertEqual(empty.payload["data"]["dismissals"], [])
        self.assertEqual(empty.payload["data"]["counts"],
                         {"name": 0, "drift": 0, "word": 0, "mention": 0, "target": 0})
        for action, kind, key in (("hide", "name", "x"), (None, "name", "x"),
                                  ("dismiss", "bogus", "x"), ("dismiss", "name", ""),
                                  ("dismiss", "name", 3), ("dismiss", "name", "x" * 1001),
                                  ("dismiss", "name", None)):
            response = self.triage(action, kind, key)
            self.assertEqual(response.status, 400, (action, kind, key))
            self.assertFalse(response.payload["ok"])
        response = self.triage("dismiss", "name", "Fate Foulers")
        self.assertEqual(response.status, 200)
        data = response.payload["data"]
        self.assertEqual([(r["kind"], r["key"]) for r in data["dismissals"]],
                         [("name", "fate foulers")])
        self.assertTrue(data["changed"])
        self.assertEqual(data["counts"]["name"], 1)
        listed = dispatch(self.request("GET", "/api/world/triage")).payload["data"]
        self.assertEqual(listed["dismissals"], data["dismissals"])
        restored = self.triage("restore", "name", "Fate Foulers").payload["data"]
        self.assertEqual(restored["dismissals"], [])
        self.assertTrue(restored["changed"])
        self.assertFalse(self.triage("restore", "name", "Fate Foulers").payload["data"]["changed"])

    def test_responses_never_expose_the_storage_location(self):
        self.triage("dismiss", "word", "zzz")
        for response in (dispatch(self.request("GET", "/api/world/triage")),
                         self.triage("dismiss", "word", "yyy"),
                         self.triage("dismiss", "bogus", "x")):
            text = json.dumps(response.payload)
            self.assertNotIn(self.private, text)
            self.assertNotIn(self.temp.name, text)
            self.assertNotIn("triage.json", text)
            self.assertNotIn(".randomwords", text)

    def test_storage_is_outside_the_vault(self):
        self.triage("dismiss", "word", "zzz")
        self.assertEqual(os.listdir(self.root), [])
        self.assertTrue(os.path.exists(os.path.join(
            self.private, world_id(self.root), "triage.json")))

    def test_write_failure_is_a_generic_500(self):
        self.triage("dismiss", "word", "zzz")
        os.chmod(os.path.join(self.private, world_id(self.root)), 0o500)
        try:
            if os.access(os.path.join(self.private, world_id(self.root)), os.W_OK):
                self.skipTest("directory permissions are not enforced here")
            response = self.triage("dismiss", "word", "other")
        finally:
            os.chmod(os.path.join(self.private, world_id(self.root)), 0o700)
        self.assertEqual(response.status, 500)
        self.assertNotIn(self.private, json.dumps(response.payload))

    def test_health_rows_carry_triage_keys_and_dismissals_filter_them(self):
        index = self.fixture()
        data = self.health(index)
        sections = data["sections"]
        self.assertEqual(data["dismissed"], {"names_without_entry": 0,
                                             "spelling_drift": 0, "unlinked_mentions": 0})
        self.assertIn("generation", data)
        phrases = [row["phrase"] for row in sections["names_without_entry"]]
        self.assertIn("Fate Foulers", phrases)
        name_row = next(r for r in sections["names_without_entry"]
                        if r["phrase"] == "Fate Foulers")
        self.assertEqual(name_row["triage"], {"kind": "name", "key": "fate foulers"})
        drift_row = next(r for r in sections["spelling_drift"]
                         if (r["from"], r["to"]) == ("alzerati", "alzarati"))
        self.assertEqual(drift_row["triage"], {"kind": "drift",
                                               "key": "alzerati→alzarati"})
        mention_rows = [r for r in sections["unlinked_mentions"]
                        if r["target_path"] == "Creatures/Aitrip.md"]
        self.assertEqual(len(mention_rows), 2)
        self.assertEqual(mention_rows[0]["triage"], {
            "kind": "mention",
            "key": mention_rows[0]["source_path"] + "|Creatures/Aitrip.md"})
        self.assertEqual(data["mention_counts"][0]["target_path"], "Creatures/Aitrip.md")
        self.assertEqual(data["mention_counts"][0]["notes"], 2)
        self.assertEqual(data["counts"]["unlinked_mentions"],
                         len(sections["unlinked_mentions"]))
        for kind in ("ambiguous_links", "name_collisions"):
            self.assertIn(kind, sections)
            self.assertEqual(data["counts"][kind], len(sections[kind]))

        for row in (name_row, drift_row, mention_rows[0]):
            self.triage("dismiss", row["triage"]["kind"], row["triage"]["key"])
        after = self.health(index)
        self.assertEqual(after["dismissed"], {"names_without_entry": 1,
                                              "spelling_drift": 1, "unlinked_mentions": 1})
        self.assertNotIn("Fate Foulers", [r["phrase"] for r in
                                          after["sections"]["names_without_entry"]])
        self.assertNotIn(("alzerati", "alzarati"), [(r["from"], r["to"]) for r in
                                                    after["sections"]["spelling_drift"]])
        remaining = [r for r in after["sections"]["unlinked_mentions"]
                     if r["target_path"] == "Creatures/Aitrip.md"]
        self.assertEqual(len(remaining), 1)
        self.assertNotEqual(remaining[0]["source_path"], mention_rows[0]["source_path"])
        self.assertEqual(after["counts"]["names_without_entry"],
                         len(after["sections"]["names_without_entry"]))
        self.assertEqual(after["mention_counts"][0]["notes"], 1)
        self.triage("restore", "name", "Fate Foulers")
        self.assertEqual(self.health(index)["dismissed"]["names_without_entry"], 0)

    def test_dismissals_belong_to_one_world(self):
        index = self.fixture()
        self.triage("dismiss", "name", "Fate Foulers")
        self.assertEqual(self.health(index)["dismissed"]["names_without_entry"], 1)
        other_root = os.path.join(self.temp.name, "other")
        os.makedirs(other_root)
        other = VaultManager(other_root,
                             os.path.join(self.temp.name, "other-recovery"))
        with open(os.path.join(other_root, "Note.md"), "w", encoding="utf-8") as output:
            output.write("We saw the Fate Foulers come. We saw the Fate Foulers leave.")
        other_index = VaultIndex(other)
        other_index.ensure_ready()
        response = dispatch(Request("GET", "/api/world/health", vault=other,
                                    world_index=other_index, fm=self.fm))
        data = response.payload["data"]
        self.assertEqual(data["dismissed"]["names_without_entry"], 0)
        self.assertIn("Fate Foulers", [r["phrase"] for r in
                                       data["sections"]["names_without_entry"]])
        listed = dispatch(Request("GET", "/api/world/triage", vault=other))
        self.assertEqual(listed.payload["data"]["dismissals"], [])

    def test_actionable_rows_drive_counts_and_mention_counts(self):
        self.note("Creatures/Aitrip.md", "A seed.")
        self.note("Cosmology/Time.md", "A god.")
        self.note("Creatures/Helay.md", "From: [[Aitrip]]\n\nAn Aitrip and some time, and ??? too.")
        self.note("Creatures/Other.md", "A second Aitrip, and [[Time]] with Time again.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        data = self.health(index)
        rows = data["sections"]["unlinked_mentions"]
        by = {(r["source_path"], r["text"]): r for r in rows}
        self.assertNotIn("???", [r["text"] for r in rows])
        self.assertTrue(by[("Creatures/Helay.md", "Aitrip")]["already_linked"])
        self.assertFalse(by[("Creatures/Helay.md", "Aitrip")]["actionable"])
        self.assertFalse(by[("Creatures/Helay.md", "time")]["actionable"])
        self.assertFalse(by[("Creatures/Other.md", "Time")]["actionable"])
        self.assertTrue(by[("Creatures/Other.md", "Aitrip")]["actionable"])
        for row in rows:
            self.assertEqual(row["actionable"], row["exact_case"] and not row["already_linked"])
        self.assertEqual(data["counts"]["unlinked_mentions"], 1)
        self.assertEqual(data["counts"]["unlinked_mentions_all"], len(rows))
        self.assertEqual(data["mention_counts"], [{
            "target_path": "Creatures/Aitrip.md", "target_title": "Aitrip",
            "notes": 1, "mentions": 1}])

    def test_target_dismissal_hides_every_mention_and_nearby_suggestion(self):
        self.note("Cosmology/Time.md", "A god.")
        self.note("Creatures/Aitrip.md", "A seed.")
        self.note("Creatures/Helay.md", "Time and Aitrip, Time again.")
        self.note("Creatures/Other.md", "Time passes near an Aitrip.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        before = self.health(index)
        row = next(r for r in before["sections"]["unlinked_mentions"]
                   if r["target_path"] == "Cosmology/Time.md")
        self.assertEqual(row["target_triage"], {"kind": "target", "key": "Cosmology/Time.md"})
        total = before["counts"]["unlinked_mentions_all"]
        hidden = sum(1 for r in before["sections"]["unlinked_mentions"]
                     if r["target_path"] == "Cosmology/Time.md")
        self.assertEqual(hidden, 3)
        self.assertEqual(self.triage("dismiss", "target", "Cosmology/Time.md").status, 200)
        after = self.health(index)
        self.assertEqual(after["dismissed"]["unlinked_mentions"], 3)
        # One dismissal hides three rows; the response says both.
        self.assertEqual(after["dismissals"]["unlinked_mentions"], 1)
        self.assertEqual(before["dismissals"]["unlinked_mentions"], 0)
        self.assertEqual(after["counts"]["unlinked_mentions_all"], total - 3)
        self.assertNotIn("Cosmology/Time.md", [r["target_path"] for r in
                                               after["sections"]["unlinked_mentions"]])
        self.assertEqual([m["target_path"] for m in after["mention_counts"]],
                         ["Creatures/Aitrip.md"])
        nearby = dispatch(self.request("POST", "/api/world/nearby", index=index, body={
            "text": "Time and Aitrip.", "path": "Draft.md", "client_revision": 1}))
        data = nearby.payload["data"]
        self.assertEqual([c["path"] for c in data["groups"]["named_not_linked"]],
                         ["Creatures/Aitrip.md"])
        self.assertNotIn("Cosmology/Time.md", [c["path"] for c in data["merged"]])
        self.triage("restore", "target", "Cosmology/Time.md")
        restored = dispatch(self.request("POST", "/api/world/nearby", index=index, body={
            "text": "Time and Aitrip.", "path": "Draft.md", "client_revision": 1}))
        self.assertEqual(len(restored.payload["data"]["groups"]["named_not_linked"]), 2)

    def test_lexicon_filters_words_and_drift_and_reports_counts(self):
        index = self.fixture()
        response = dispatch(self.request("GET", "/api/world/lexicon", index=index))
        data = response.payload["data"]
        self.assertEqual(data["dismissed"], {"entries": 0, "drift": 0})
        self.assertIn("generation", data)
        words = {row["word"]: row for row in data["entries"]}
        self.assertEqual(words["alzarati"]["triage"], {"kind": "word", "key": "alzarati"})
        pair = next(r for r in data["drift"] if (r["from"], r["to"]) == ("alzerati", "alzarati"))
        self.assertEqual(pair["triage"]["key"], "alzerati→alzarati")

        self.triage("dismiss", "drift", pair["triage"]["key"])
        data = dispatch(self.request("GET", "/api/world/lexicon", index=index)).payload["data"]
        self.assertEqual(data["dismissed"], {"entries": 0, "drift": 1})
        self.assertEqual(data["dismissals"], {"entries": 0, "drift": 1})
        self.assertNotIn(("alzerati", "alzarati"), [(r["from"], r["to"]) for r in data["drift"]])
        self.assertIn("alzarati", [r["word"] for r in data["entries"]])

        self.triage("restore", "drift", pair["triage"]["key"])
        self.triage("dismiss", "word", "Alzerati")
        data = dispatch(self.request("GET", "/api/world/lexicon", index=index)).payload["data"]
        self.assertEqual(data["dismissed"]["entries"], 1)
        self.assertNotIn("alzerati", [r["word"] for r in data["entries"]])
        # A pair with a dismissed word is not offered as drift either.
        self.assertNotIn(("alzerati", "alzarati"), [(r["from"], r["to"]) for r in data["drift"]])
        self.assertEqual(data["dismissed"]["drift"], 1)
        self.assertEqual(data["dismissals"], {"entries": 1, "drift": 0})
        health = self.health(index)
        self.assertNotIn(("alzerati", "alzarati"),
                         [(r["from"], r["to"]) for r in health["sections"]["spelling_drift"]])


if __name__ == "__main__":
    unittest.main()
