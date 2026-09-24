import os
import tempfile
import unittest
from types import SimpleNamespace

from entry import parse

from vault import VaultManager
from vault_index import VaultIndex
from web_routes import Request
from world_routes import dispatch


class WorldRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.temp.name, "vault")
        self.recovery = os.path.join(self.temp.name, "recovery")
        os.mkdir(self.root)
        os.makedirs(os.path.join(self.root, "Places"))
        os.makedirs(os.path.join(self.root, "People"))
        with open(os.path.join(self.root, "Places", "Fenaya.md"), "w", encoding="utf8") as f:
            f.write("A green valley. [[Mira]]\n")
        with open(os.path.join(self.root, "People", "Mira.md"), "w", encoding="utf8") as f:
            f.write("From: [[Fenaya]]\n\nMira explores [[Fenaya]] in the green valley. #Loaming\n")
        os.makedirs(os.path.join(self.root, "Templates"))
        with open(os.path.join(self.root, "Templates", "Creature.md"), "w", encoding="utf8") as f:
            f.write("## Facts\n\nThe template body.\n")
        self.vault = VaultManager(self.root, self.recovery)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, method, path, query=None, body=None, world_index=None):
        return Request(method, path, query or {}, body or {}, vault=self.vault,
                       world_index=world_index)

    def test_tree_and_entry_read_return_specified_data(self):
        response = dispatch(self.request("GET", "/api/world/tree", {"path": "People"}))
        self.assertEqual(response.status, 200)
        data = response.payload["data"]
        self.assertEqual(data["path"], "People")
        self.assertEqual(data["entries"][0]["path"], "People/Mira.md")
        self.assertEqual(data["entries"][0]["name"], "Mira.md")
        self.assertFalse(data["entries"][0]["is_dir"])

        opened = dispatch(self.request("GET", "/api/world/entry", {"path": "People/Mira.md"}))
        self.assertEqual(opened.status, 200)
        self.assertEqual(opened.payload["data"]["text"], "From: [[Fenaya]]\n\nMira explores [[Fenaya]] in the green valley. #Loaming\n")
        self.assertTrue(opened.payload["data"]["revision"].startswith("sha256:"))
        self.assertIn("Mira explores", opened.payload["data"]["html"])

    def test_search_finds_titles_and_body_text(self):
        response = dispatch(self.request("GET", "/api/world/search", {"q": "A green valley"}))
        self.assertEqual(response.status, 200)
        self.assertEqual([x["path"] for x in response.payload["data"]["results"]], ["Places/Fenaya.md"])

    def test_tags_combines_index_and_root_tags_file_sorted_and_deduplicated(self):
        with open(os.path.join(self.root, "Tags.md"), "w", encoding="utf8") as f:
            f.write("# Tags\n\n- #animal\n- #loaming — duplicate spelling\n- biome\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("GET", "/api/world/tags", world_index=index))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload["data"]["tags"], ["animal", "biome", "loaming"])

    def test_save_success_preserves_revision_contract_and_conflict_returns_current(self):
        text, revision = self.vault.read("Places/Fenaya.md")
        saved = dispatch(self.request("POST", "/api/world/entry", body={
            "path": "Places/Fenaya.md", "text": "New content\n", "revision": revision,
        }))
        self.assertEqual(saved.status, 200)
        self.assertEqual(saved.payload["data"]["revision"], self.vault.read("Places/Fenaya.md")[1])

        stale = dispatch(self.request("POST", "/api/world/entry", body={
            "path": "Places/Fenaya.md", "text": "stale edit", "revision": revision,
        }))
        self.assertEqual(stale.status, 409)
        self.assertEqual(stale.payload["data"]["text"], "New content\n")
        self.assertEqual(stale.payload["data"]["revision"], saved.payload["data"]["revision"])

        disk_path = os.path.join(self.root, "Places", "Fenaya.md")
        with open(disk_path, "w", encoding="utf8") as f:
            f.write("external edit\n")
        _, current_revision = self.vault.read("Places/Fenaya.md")
        replaced = dispatch(self.request("POST", "/api/world/entry", body={
            "path": "Places/Fenaya.md", "text": "Reviewed replacement\n",
            "revision": revision, "replace_revision": current_revision,
        }))
        self.assertEqual(replaced.status, 200)
        self.assertEqual(replaced.payload["data"]["recovery"], replaced.payload["data"]["recovery_path"])
        self.assertTrue(os.path.isfile(replaced.payload["data"]["recovery"]))

    def test_create_exclusive_validates_and_collisions_are_409(self):
        body = {"folder": "People", "title": "New Person", "from_targets": ["Places/Fenaya.md"],
                "tags": ["loaming"], "origin": ["seedword"], "template": "Templates/Creature.md"}
        created = dispatch(self.request("POST", "/api/world/new", body=body))
        self.assertEqual(created.status, 200)
        text, revision = self.vault.read("People/New Person.md")
        self.assertIn("From: [[Places/Fenaya]]", text)
        self.assertIn("#loaming", text)
        self.assertIn("Origin: seedword", text)
        self.assertIn("The template body.", text)
        self.assertTrue(revision.startswith("sha256:"))
        self.assertEqual(dispatch(self.request("POST", "/api/world/new", body=body)).status, 409)

        invalid = dispatch(self.request("POST", "/api/world/new", body={**body, "tags": "loaming"}))
        self.assertEqual(invalid.status, 400)

        missing_folder = dispatch(self.request("POST", "/api/world/new", body={**body, "title": "Elsewhere", "folder": "Missing"}))
        self.assertEqual(missing_folder.status, 400)
        noncanonical_source = dispatch(self.request("POST", "/api/world/new", body={
            **body, "title": "Bad Source", "from_targets": ["Places/../Places/Fenaya.md"]}))
        self.assertEqual(noncanonical_source.status, 400)

    def test_template_path_is_read_from_vault_and_invalid_template_is_rejected(self):
        plain = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "No Template", "template": None}))
        self.assertEqual(plain.status, 200)
        response = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Template User", "template": "Templates/Creature.md"}))
        self.assertEqual(response.status, 200)
        text, _ = self.vault.read("People/Template User.md")
        self.assertIn("## Facts", text)
        invalid = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Bad Template", "template": "Templates/Missing.md"}))
        self.assertEqual(invalid.status, 400)
        outside = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Outside Template", "template": "People/Mira.md"}))
        self.assertEqual(outside.status, 400)
        no_template = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "No Template Unique", "template": None}))
        self.assertEqual(no_template.status, 200)

    def test_entry_uses_source_aware_resolution_and_backlinks_include_sentence(self):
        source, _ = self.vault.read("People/Mira.md")
        source_entry = SimpleNamespace(path="People/Mira.md", title="Mira", raw=source)
        target_entry = SimpleNamespace(path="Places/Fenaya.md", title="Fenaya", raw="A green valley. [[Mira]]\n")
        link = parse(source, "People/Mira.md").links[1]

        class Index:
            entries = {"People/Mira.md": source_entry, "Places/Fenaya.md": target_entry}
            backlinks = {"Places/Fenaya.md": (("People/Mira.md", link),)}
            def ensure_ready(self):
                pass
            def resolve(self, target, source_path=None):
                self.source_path = source_path
                return SimpleNamespace(path="Places/Fenaya.md", status="resolved")
            def entry(self, path):
                return self.entries.get(path)

        index = Index()
        response = dispatch(self.request("GET", "/api/world/entry", {"path": "Places/Fenaya.md"}, world_index=index))
        self.assertEqual(response.status, 200)
        self.assertEqual(index.source_path, "Places/Fenaya.md")
        backlink = response.payload["data"]["backlinks"][0]
        self.assertEqual(backlink["path"], "People/Mira.md")
        self.assertIn("Mira explores [[Fenaya]]", backlink["context"])

    def test_real_index_duplicate_resolution_backlinks_nearby_and_utf16(self):
        os.makedirs(os.path.join(self.root, "Things", "Alpha"))
        os.makedirs(os.path.join(self.root, "Things", "Beta"))
        with open(os.path.join(self.root, "Things", "Alpha", "Shared.md"), "w", encoding="utf8") as f:
            f.write("---\naliases: SpecificShared\n---\nFirst shared note.\n")
        with open(os.path.join(self.root, "Things", "Beta", "Shared.md"), "w", encoding="utf8") as f:
            f.write("Second shared note.\n")
        with open(os.path.join(self.root, "Things", "Alpha", "Resolver.md"), "w", encoding="utf8") as f:
            f.write("Local [[Shared]]; qualified [[Things/Beta/Shared]].\n")
        index = VaultIndex(self.vault, stat_interval=3600)

        opened = dispatch(self.request("GET", "/api/world/entry", {
            "path": "Things/Alpha/Resolver.md"}, world_index=index))
        self.assertEqual(opened.status, 200)
        data = opened.payload["data"]
        self.assertIn('href="/world/entry?path=Things/Alpha/Shared.md"', data["html"])
        self.assertIn('href="/world/entry?path=Things/Beta/Shared.md"', data["html"])
        shared = next(link for link in data["links"] if link["target"] == "Shared")
        self.assertEqual(shared["resolved_path"], "Things/Alpha/Shared.md")
        self.assertEqual(shared["status"], "resolved")

        backlinks = dispatch(self.request("GET", "/api/world/entry", {
            "path": "Places/Fenaya.md"}, world_index=index)).payload["data"]["backlinks"]
        mira = next(row for row in backlinks if row["path"] == "People/Mira.md" and
                    "Mira explores [[Fenaya]]" in row["context"])
        self.assertIn("Mira explores [[Fenaya]]", mira["context"])

        text = "😀 Fenaya and SpecificShared"
        nearby = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": text, "path": "Draft.md", "client_revision": "r1",
        }, world_index=index))
        self.assertEqual(nearby.status, 200)
        named = nearby.payload["data"]["groups"]["named_not_linked"]
        fenaya = next(card for card in named if card["expected"] == "Fenaya")
        self.assertEqual((fenaya["start"], fenaya["end"]), (3, 9))
        specific = next(card for card in named if card["expected"] == "SpecificShared")
        self.assertEqual(specific["link_target"], "Things/Alpha/Shared")

    def test_nearby_returns_client_revision_and_safe_preview(self):
        response = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": "<script>bad</script> [[Fenaya]]", "path": "Draft.md", "client_revision": 7,
        }))
        self.assertEqual(response.status, 200)
        data = response.payload["data"]
        self.assertEqual(data["client_revision"], 7)
        self.assertIn("&lt;script&gt;", data["html"])
        self.assertEqual(set(data["groups"]), {"named_not_linked", "same_biome", "same_tags"})

    def test_invalid_and_unknown_routes_have_envelopes(self):
        self.assertEqual(dispatch(self.request("GET", "/api/world/tree", {"path": "../"})).status, 400)
        unknown = dispatch(self.request("GET", "/api/world/nope"))
        self.assertEqual(unknown.status, 404)
        self.assertFalse(unknown.payload["ok"])


if __name__ == "__main__":
    unittest.main()
