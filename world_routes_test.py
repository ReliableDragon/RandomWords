import os
import tempfile
import unittest
from types import SimpleNamespace

from entry import parse
from file_manager import FileManager

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

    def request(self, method, path, query=None, body=None, world_index=None,
                session=None, fm=None, word_index=None):
        return Request(method, path, query or {}, body or {}, vault=self.vault,
                       world_index=world_index, session=session, fm=fm,
                       word_index=word_index)

    def test_phase_two_reports_lexicon_and_roller_use_canonical_paths(self):
        os.makedirs(os.path.join(self.root, "Locations", "Biomes"))
        with open(os.path.join(self.root, "Locations", "Biomes", "Fenaya.md"),
                  "w", encoding="utf8") as f:
            f.write("Green valley biome.\n")
        with open(os.path.join(self.root, "People", "Mira.md"),
                  "w", encoding="utf8") as f:
            f.write("From: [[Locations/Biomes/Fenaya]]\n\nAlzerati glimmers here. #rework\n")
        with open(os.path.join(self.root, "How-To.md"), "w", encoding="utf8") as f:
            f.write("# Cheat Sheet\nMisconceptions\nMemory\n## Methods/Tools\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        fm = FileManager()
        session = SimpleNamespace(active_words=lambda: ["showful", "arthrosporic"])

        matrix = dispatch(self.request("GET", "/api/world/matrix", world_index=index))
        self.assertEqual(matrix.status, 200)
        row = next(row for row in matrix.payload["data"]["rows"]
                   if row["path"] == "Locations/Biomes/Fenaya.md")
        self.assertIn("People/Mira.md", [entry["path"] for entry in
                                      row["cells"]["People"]["entries"]])

        health = dispatch(self.request("GET", "/api/world/health", world_index=index, fm=fm))
        self.assertEqual(health.status, 200)
        self.assertIn("People/Mira.md", [row["path"] for row in
                                         health.payload["data"]["sections"]["rework"]])

        lexicon = dispatch(self.request("GET", "/api/world/lexicon", {"q": "alzerati"},
                                        world_index=index, fm=fm))
        self.assertEqual(lexicon.status, 200)
        word = next(row for row in lexicon.payload["data"]["entries"]
                    if row["word"] == "alzerati")
        self.assertEqual(word["uses"][0]["path"], "People/Mira.md")

        roll = dispatch(self.request("POST", "/api/world/roll", body={"entry": "People/Mira.md"},
                                     world_index=index, session=session))
        self.assertEqual(roll.status, 200)
        self.assertEqual(roll.payload["data"]["entry"]["path"], "People/Mira.md")

    def test_backlog_creation_strikes_exact_idea_and_reports_stale_idea(self):
        os.makedirs(os.path.join(self.root, "Ideas"))
        with open(os.path.join(self.root, "Ideas", "List.md"), "w", encoding="utf8") as f:
            f.write("# Ideas\n* A lantern made of rain\n* Another idea\n")
        listed = dispatch(self.request("GET", "/api/world/backlog"))
        self.assertEqual(listed.status, 200)
        first, second = listed.payload["data"]["ideas"]
        created = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Lantern Maker", "idea": first}))
        self.assertEqual(created.status, 200)
        self.assertTrue(created.payload["data"]["idea_updated"])
        self.assertIn("~~A lantern made of rain~~", self.vault.read("Ideas/List.md")[0])

        stale = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Second Maker", "idea": second}))
        self.assertEqual(stale.status, 200)
        self.assertFalse(stale.payload["data"]["idea_updated"])
        self.assertTrue(self.vault.read("People/Second Maker.md")[1])
        self.assertIn("* Another idea", self.vault.read("Ideas/List.md")[0])

    def test_tree_and_entry_read_return_specified_data(self):
        response = dispatch(self.request("GET", "/api/world/tree", {"path": "People"}))
        self.assertEqual(response.status, 200)
        data = response.payload["data"]
        self.assertEqual(data["path"], "People")
        self.assertEqual(data["entries"][0]["path"], "People/Mira.md")
        self.assertEqual(data["entries"][0]["name"], "Mira.md")
        self.assertFalse(data["entries"][0]["is_dir"])
        self.assertRegex(data["vault_id"], r"^[0-9a-f]{16}$")

        opened = dispatch(self.request("GET", "/api/world/entry", {"path": "People/Mira.md"}))
        self.assertEqual(opened.status, 200)
        self.assertEqual(opened.payload["data"]["text"], "From: [[Fenaya]]\n\nMira explores [[Fenaya]] in the green valley. #Loaming\n")
        self.assertTrue(opened.payload["data"]["revision"].startswith("sha256:"))
        self.assertIn("Mira explores", opened.payload["data"]["html"])

    def test_tree_vault_id_is_stable_per_vault_and_changes_for_another_root(self):
        root_tree = dispatch(self.request("GET", "/api/world/tree"))
        people_tree = dispatch(self.request("GET", "/api/world/tree", {"path": "People"}))
        self.assertEqual(root_tree.status, 200)
        self.assertEqual(root_tree.payload["data"]["vault_id"],
                         people_tree.payload["data"]["vault_id"])

        other_root = os.path.join(self.temp.name, "other-vault")
        os.mkdir(other_root)
        other_vault = VaultManager(other_root, self.recovery)
        other_request = Request("GET", "/api/world/tree", {}, {}, vault=other_vault)
        other_tree = dispatch(other_request)
        self.assertNotEqual(root_tree.payload["data"]["vault_id"],
                            other_tree.payload["data"]["vault_id"])

    def test_save_invalidates_reports_immediately(self):
        index = VaultIndex(self.vault, stat_interval=3600)
        fm = FileManager()
        before = dispatch(self.request("GET", "/api/world/lexicon", {"q": "qzorthax"},
                                       world_index=index, fm=fm))
        self.assertEqual(before.payload["data"]["entries"], [])
        text, revision = self.vault.read("Places/Fenaya.md")
        saved = dispatch(self.request("POST", "/api/world/entry", body={
            "path": "Places/Fenaya.md", "text": text + "Qzorthax grows here.\n",
            "revision": revision,
        }, world_index=index))
        self.assertEqual(saved.status, 200)
        after = dispatch(self.request("GET", "/api/world/lexicon", {"q": "qzorthax"},
                                      world_index=index, fm=fm))
        self.assertEqual([row["word"] for row in after.payload["data"]["entries"]],
                         ["qzorthax"])

    def test_search_finds_titles_and_body_text(self):
        response = dispatch(self.request("GET", "/api/world/search", {"q": "A green valley"}))
        self.assertEqual(response.status, 200)
        self.assertEqual([x["path"] for x in response.payload["data"]["results"]], ["Places/Fenaya.md"])

    def test_search_says_how_each_result_matched(self):
        with open(os.path.join(self.root, "Places", "Fenaya.md"), "w", encoding="utf8") as f:
            f.write("---\naliases: Vale of Green\n---\nThe old  road\nwinds past a quiet reservoir "
                    + "and " * 60 + "ends.\n")
        index = VaultIndex(self.vault, stat_interval=3600)

        def rows(q):
            response = dispatch(self.request("GET", "/api/world/search", {"q": q}, world_index=index))
            return {row["path"]: row for row in response.payload["data"]["results"]}

        self.assertEqual(rows("fenaya")["Places/Fenaya.md"]["match"], "title")
        alias = rows("vale of")["Places/Fenaya.md"]
        self.assertEqual((alias["match"], alias["matched_alias"]), ("alias", "Vale of Green"))
        self.assertNotIn("snippet", alias)
        hit = rows("RESERVOIR")["Places/Fenaya.md"]
        self.assertEqual(hit["match"], "text")
        start, end = hit["snippet_match"]
        self.assertEqual(hit["snippet"][start:end].casefold(), "reservoir")
        self.assertIn("road winds past a quiet", hit["snippet"])
        self.assertNotIn("\n", hit["snippet"])
        self.assertLessEqual(len(hit["snippet"]), 125)

    def test_graph_has_canonical_entry_nodes_and_distinct_link_states(self):
        os.makedirs(os.path.join(self.root, "Other"))
        os.makedirs(os.path.join(self.root, "Elsewhere"))
        for path, text in (
            ("People/Duplicate.md", "First duplicate.\n"),
            ("Places/Duplicate.md", "Second duplicate.\n"),
            ("Elsewhere/Links.md", "[[Duplicate]] [[Missing]] [[People/Duplicate]]\n"),
            ("Other/Isolated.md", "Nothing links here.\n"),
        ):
            with open(os.path.join(self.root, *path.split("/")), "w", encoding="utf8") as f:
                f.write(text)
        os.makedirs(os.path.join(self.root, ".obsidian"))
        with open(os.path.join(self.root, ".obsidian", "graph.json"), "w", encoding="utf8") as f:
            f.write('{"colorGroups":[{"query":"path:People  ","color":{"rgb":14701138}}]}')

        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("GET", "/api/world/graph", world_index=index))
        self.assertEqual(response.status, 200)
        data = response.payload["data"]
        nodes = {node["id"]: node for node in data["nodes"]}
        self.assertIn("People/Duplicate.md", nodes)
        self.assertEqual(nodes["People/Duplicate.md"]["color"], "#e05252")
        self.assertIn("Places/Duplicate.md", nodes)
        self.assertIn("Other/Isolated.md", nodes)
        self.assertIn("ambiguous:duplicate", nodes)
        self.assertIn("unresolved:missing", nodes)
        ambiguous = nodes["ambiguous:duplicate"]
        self.assertEqual(ambiguous["state"], "ambiguous")
        self.assertEqual(ambiguous["candidates"], ["People/Duplicate.md", "Places/Duplicate.md"])
        resolved = next(edge for edge in data["edges"]
                        if edge["source"] == "Elsewhere/Links.md" and
                        edge["label"] == "People/Duplicate")
        self.assertEqual(resolved["target"], "People/Duplicate.md")
        self.assertEqual(resolved["status"], "resolved")

    def test_graph_marks_scaffolding_as_outside_the_world(self):
        os.makedirs(os.path.join(self.root, "Ideas"))
        for path in ("Ideas/Someday.md", "Loose.md"):
            with open(os.path.join(self.root, *path.split("/")), "w", encoding="utf8") as f:
                f.write("[[Missing]]\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("GET", "/api/world/graph", world_index=index))
        nodes = {node["id"]: node for node in response.payload["data"]["nodes"]}
        self.assertIs(nodes["People/Mira.md"]["world"], True)
        self.assertIs(nodes["Templates/Creature.md"]["world"], False)
        self.assertIs(nodes["Ideas/Someday.md"]["world"], False)
        self.assertIs(nodes["Loose.md"]["world"], False)
        self.assertIsNone(nodes["unresolved:missing"]["world"])

    def test_graph_around_uses_canonical_path_and_depth(self):
        os.makedirs(os.path.join(self.root, "Other"))
        with open(os.path.join(self.root, "Other", "Far.md"), "w", encoding="utf8") as f:
            f.write("Far note.\n")
        with open(os.path.join(self.root, "People", "Mira.md"), "w", encoding="utf8") as f:
            f.write("From: [[Fenaya]]\n\nMira explores [[Fenaya]] and [[Missing]].\n")
        with open(os.path.join(self.root, "Other", "Far.md"), "w", encoding="utf8") as f:
            f.write("[[People/Mira]]\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("GET", "/api/world/graph",
                                         {"around": "Places/Fenaya.md", "depth": "1"},
                                         world_index=index))
        self.assertEqual(response.status, 200)
        data = response.payload["data"]
        node_ids = {node["id"] for node in data["nodes"]}
        self.assertEqual(data["around"], "Places/Fenaya.md")
        self.assertEqual(data["depth"], 1)
        self.assertIn("People/Mira.md", node_ids)
        self.assertNotIn("Other/Far.md", node_ids)
        self.assertIn("unresolved:missing", node_ids)
        invalid = dispatch(self.request("GET", "/api/world/graph",
                                        {"around": "Fenaya"}, world_index=index))
        self.assertEqual(invalid.status, 400)

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

    def test_create_folder_allows_empty_destinations_and_rejects_invalid_or_colliding_names(self):
        index = VaultIndex(self.vault, stat_interval=3600)
        root_folder = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "", "name": "Chronicles",
        }, world_index=index))
        self.assertEqual(root_folder.status, 200)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "Chronicles")))
        created = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "People", "name": "Lineages",
        }, world_index=index))
        self.assertEqual(created.status, 200)
        self.assertEqual(created.payload["data"]["path"], "People/Lineages")
        self.assertTrue(os.path.isdir(os.path.join(self.root, "People", "Lineages")))

        # Empty folders are visible in the tree and immediately usable as a
        # note destination; notes are not required to make them persistent.
        listed = dispatch(self.request("GET", "/api/world/tree", {"path": "People"}))
        self.assertIn({"path": "People/Lineages", "name": "Lineages", "is_dir": True,
                       "words": 0, "stub": False}, listed.payload["data"]["entries"])
        note = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People/Lineages", "title": "First Family",
        }))
        self.assertEqual(note.status, 200)

        collision = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "People", "name": "lineages",
        }))
        self.assertEqual(collision.status, 409)
        file_collision = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "People", "name": "Mira.md",
        }))
        self.assertEqual(file_collision.status, 409)
        accented = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "", "name": "Café",
        }))
        self.assertEqual(accented.status, 200)
        unicode_collision = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "", "name": "Cafe\u0301",
        }))
        self.assertEqual(unicode_collision.status, 409)

        outside = os.path.join(self.temp.name, "outside")
        os.mkdir(outside)
        os.symlink(outside, os.path.join(self.root, "Outside"))
        outside_parent = dispatch(self.request("POST", "/api/world/folder", body={
            "parent": "Outside", "name": "Escape",
        }))
        self.assertEqual(outside_parent.status, 400)
        for body in (
            {"parent": "People", "name": "../Escape"},
            {"parent": "People/../People", "name": "Safe"},
            {"parent": "People", "name": ".hidden"},
            {"parent": "Missing", "name": "Safe"},
        ):
            self.assertEqual(dispatch(self.request("POST", "/api/world/folder", body=body)).status, 400)

    def test_create_metadata_headers_round_trip_before_tags_and_template(self):
        response = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Round Trip", "from_targets": ["Places/Fenaya.md"],
            "origin": ["rainseed (a lantern made by rain)"], "tags": ["loaming"], "template": "Templates/Creature.md",
        }))
        self.assertEqual(response.status, 200)
        text, _ = self.vault.read("People/Round Trip.md")
        self.assertLess(text.index("From:"), text.index("Origin:"))
        self.assertLess(text.index("Origin:"), text.index("#loaming"))
        entry = parse(text, "People/Round Trip.md")
        self.assertEqual([link.target for link in entry.from_targets], ["Places/Fenaya"])
        self.assertEqual(entry.origin, ["rainseed"])
        self.assertEqual(entry.glosses, {"rainseed": "a lantern made by rain"})
        self.assertIn("loaming", entry.tags)

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
        self.assertEqual(set(data["groups"]), {
            "named_not_linked", "same_biome", "same_tags", "talks_about_same_things",
            "linked_from_what_you_link"})
        self.assertEqual(data["merged"], [])
        self.assertEqual(data["skipped"], [])

    def test_nearby_returns_parsed_draft_metadata_without_raw_text(self):
        response = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": "From: [[Places/Fenaya]]\nOrigin: rainseed (a lantern)\n#loaming\n\nDraft.\n",
            "path": "Draft.md", "client_revision": "draft-2",
        }))
        self.assertEqual(response.status, 200)
        metadata = response.payload["data"]["metadata"]
        self.assertEqual([link["target"] for link in metadata["from_targets"]], ["Places/Fenaya"])
        self.assertEqual(metadata["glosses"], {"rainseed": "a lantern"})
        self.assertEqual(metadata["tags"], ["loaming"])
        self.assertNotIn("raw", metadata)

    def test_nearby_omits_structural_templates_and_tag_index(self):
        with open(os.path.join(self.root, "Tags.md"), "w", encoding="utf8") as f:
            f.write("Tag reference. #loaming\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": "Creature and Tags. #loaming\n", "path": "Draft.md",
            "client_revision": "draft-3",
        }, world_index=index))
        self.assertEqual(response.status, 200)
        paths = [card.get("path") for cards in response.payload["data"]["groups"].values()
                 for card in cards if isinstance(card, dict)]
        self.assertNotIn("Templates/Creature.md", paths)
        self.assertNotIn("Tags.md", paths)

    def test_entry_and_nearby_evaluate_supported_bases_and_diagnose_unsupported(self):
        os.makedirs(os.path.join(self.root, "Locations", "Biomes"))
        os.makedirs(os.path.join(self.root, "Flora and Fauna"))
        biome_path = "Locations/Biomes/Fenaya.md"
        biome_text = (
            "# Wildlife\n"
            "```base\nfilters:\n  and:\n"
            "    - file.links.contains(this.file.name)\n"
            "    - file.path.contains(\"Flora and Fauna\")\n``````\n"
            "# Future Filter\n"
            "```base\nfilters:\n  and:\n"
            "    - file.name.contains(\"Heron\")\n```\n"
        )
        with open(os.path.join(self.root, biome_path), "w", encoding="utf8") as f:
            f.write(biome_text)
        with open(os.path.join(self.root, "Flora and Fauna", "Marsh Heron.md"),
                  "w", encoding="utf8") as f:
            f.write("From: [[Locations/Biomes/Fenaya]]\n\nA marsh bird.\n")
        index = VaultIndex(self.vault, stat_interval=3600)

        opened = dispatch(self.request("GET", "/api/world/entry", {"path": biome_path},
                                       world_index=index))
        preview = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": biome_text, "path": biome_path, "client_revision": "draft-1",
        }, world_index=index))
        self.assertEqual((opened.status, preview.status), (200, 200))
        for html in (opened.payload["data"]["html"], preview.payload["data"]["html"]):
            self.assertIn("class=\"base-results\"", html)
            self.assertIn("path=Flora%20and%20Fauna/Marsh%20Heron.md", html)
            self.assertIn("class=\"base-diagnostic\"", html)
            self.assertIn("Unsupported Base filter expression", html)
            self.assertIn("<pre><code>", html)

    def test_invalid_and_unknown_routes_have_envelopes(self):
        self.assertEqual(dispatch(self.request("GET", "/api/world/tree", {"path": "../"})).status, 400)
        unknown = dispatch(self.request("GET", "/api/world/nope"))
        self.assertEqual(unknown.status, 404)
        self.assertFalse(unknown.payload["ok"])

    def test_story_quotes_and_export_routes_use_configured_folders(self):
        os.makedirs(os.path.join(self.root, "Story"))
        with open(os.path.join(self.root, "Story", "One.md"), "w", encoding="utf8") as f:
            f.write("---\nwhen: 1\nwho: [\"[[Mira]]\"]\n---\nMira visits [[Places/Fenaya]].\n")
        with open(os.path.join(self.root, "People", "Mira.md"), "w", encoding="utf8") as f:
            f.write("Mira.\n\n> The valley endures.\n- [[Mira]]\n")
        index = VaultIndex(self.vault, stat_interval=3600, story_folders=["Story"])
        story = dispatch(self.request("GET", "/api/world/story", world_index=index))
        self.assertEqual(story.status, 200)
        self.assertEqual(story.payload["data"]["scenes"][0]["path"], "Story/One.md")
        self.assertEqual(story.payload["data"]["scenes"][0]["who"][0]["path"], "People/Mira.md")
        quote = dispatch(self.request("GET", "/api/world/quotes", {"by": "People/Mira.md"},
                         world_index=index))
        self.assertEqual(quote.status, 200)
        self.assertEqual(quote.payload["data"]["quotes"][0]["speaker"]["path"], "People/Mira.md")
        exported = dispatch(self.request("GET", "/api/world/export", {"path": "story"},
                            world_index=index))
        self.assertEqual(exported.status, 200)
        self.assertIn("Story/One.md", exported.payload["data"]["entries"])
        invalid = dispatch(self.request("GET", "/api/world/quotes", {"by": "Mira"},
                           world_index=index))
        self.assertEqual(invalid.status, 400)

    def test_story_entry_exposes_frontmatter_diagnostics(self):
        os.makedirs(os.path.join(self.root, "Story"))
        with open(os.path.join(self.root, "Story", "Broken.md"), "w", encoding="utf8") as f:
            f.write("---\nwhen: later\n---\nDraft.\n")
        index = VaultIndex(self.vault, stat_interval=3600, story_folders=["Story"])
        opened = dispatch(self.request("GET", "/api/world/entry", {"path": "Story/Broken.md"},
                                       world_index=index))
        self.assertEqual(opened.status, 200)
        self.assertIn("Story `when` must be an integer", opened.payload["data"]["diagnostics"][0])

    def test_status_reports_generation_and_every_index_route_carries_it(self):
        os.makedirs(os.path.join(self.root, "Ideas"))
        with open(os.path.join(self.root, "Ideas", "List.md"), "w", encoding="utf8") as f:
            f.write("# Ideas\n* A lantern made of rain\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        fm = FileManager()
        missing = dispatch(self.request("GET", "/api/world/status"))
        self.assertEqual(missing.status, 404)

        status = dispatch(self.request("GET", "/api/world/status", world_index=index))
        self.assertEqual(status.status, 200)
        self.assertEqual(status.payload["data"], {"generation": 1})
        self.assertEqual(dispatch(self.request("GET", "/api/world/status",
                                               world_index=index)).payload["data"],
                         {"generation": 1})

        def data(route, query=None, **kwargs):
            response = dispatch(self.request("GET", route, query, world_index=index,
                                             fm=fm, **kwargs))
            self.assertEqual(response.status, 200, route)
            return response.payload["data"]

        for route, query in (("/api/world/matrix", None), ("/api/world/health", None),
                             ("/api/world/lexicon", None), ("/api/world/story", None),
                             ("/api/world/backlog", None), ("/api/world/graph", None),
                             ("/api/world/entry", {"path": "People/Mira.md"})):
            self.assertEqual(data(route, query)["generation"], 1, route)
        nearby = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": "Draft.", "path": "Draft.md", "client_revision": 1}, world_index=index))
        self.assertEqual(nearby.payload["data"]["generation"], 1)

        text, revision = self.vault.read("People/Mira.md")
        saved = dispatch(self.request("POST", "/api/world/entry", body={
            "path": "People/Mira.md", "text": text + "More.\n", "revision": revision},
            world_index=index))
        self.assertEqual(saved.status, 200)
        self.assertEqual(saved.payload["data"]["generation"], 2)
        self.assertEqual(saved.payload["data"]["revision"], self.vault.read("People/Mira.md")[1])
        created = dispatch(self.request("POST", "/api/world/new", body={
            "folder": "People", "title": "Newcomer"}, world_index=index))
        self.assertEqual(created.status, 200)
        self.assertEqual(created.payload["data"]["generation"], 3)
        self.assertEqual(data("/api/world/status")["generation"], 3)
        # The pre-existing response fields are still there.
        self.assertIn("revision", saved.payload["data"])
        self.assertEqual(created.payload["data"]["path"], "People/Newcomer.md")

    def test_generation_is_null_without_an_index(self):
        opened = dispatch(self.request("GET", "/api/world/entry", {"path": "People/Mira.md"}))
        self.assertIsNone(opened.payload["data"]["generation"])

    def test_nearby_route_returns_merged_cards_with_flags_and_skipped_kinds(self):
        with open(os.path.join(self.root, "Places", "Fenaya.md"), "w", encoding="utf8") as f:
            f.write("---\naliases: The Valley\n---\nA green valley. #loaming\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("POST", "/api/world/nearby", body={
            "text": "We walked into The Valley. #loaming\n\n![[map.png]]\n\n- [ ] pack\n",
            "path": "Draft.md", "client_revision": "r1"}, world_index=index))
        data = response.payload["data"]
        self.assertEqual(data["skipped"], ["embed", "task"])
        self.assertIn('data-kind="embed"', data["html"])
        merged = data["merged"]
        self.assertEqual(merged[0]["path"], "Places/Fenaya.md")
        reasons = {r["group"]: r for r in merged[0]["reasons"]}
        self.assertEqual(reasons["named_not_linked"]["expected"], "The Valley")
        self.assertEqual(reasons["named_not_linked"]["client_revision"], "r1")
        self.assertIn("same_tags", reasons)
        self.assertFalse(merged[0]["is_place"])
        self.assertFalse(merged[0]["namesake"])
        self.assertEqual(data["groups"]["named_not_linked"][0]["path"], "Places/Fenaya.md")
        self.assertIn("is_place", data["groups"]["named_not_linked"][0])
        self.assertTrue(all(not c["path"].startswith("Templates/") for c in merged))

    def test_entry_read_reports_skipped_constructs(self):
        with open(os.path.join(self.root, "People", "Mira.md"), "w", encoding="utf8") as f:
            f.write("| a | b |\n| - | - |\n| 1 | 2 |\n\n![x](y.png)\n")
        opened = dispatch(self.request("GET", "/api/world/entry", {"path": "People/Mira.md"}))
        self.assertEqual(opened.payload["data"]["skipped"], ["table", "image"])

    def test_health_reports_new_sections_and_passes_the_word_index(self):
        for path, text in (("Creatures/Aitrip.md", "A seed."),
                           ("Creatures/Helay.md", "Helay meets an Aitrip. [[Twin]]"),
                           ("A/Twin.md", "one"), ("B/Twin.md", "two")):
            full = os.path.join(self.root, *path.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf8") as f:
                f.write(text)
        index = VaultIndex(self.vault, stat_interval=3600)
        seen = []

        class Words:
            def ensure_ready(self):
                seen.append("ready")

            def texts_for(self, word):
                return ["Some Book"]

            def doc_count(self, word):
                return 1
        response = dispatch(self.request("GET", "/api/world/health", world_index=index,
                                         fm=FileManager(), word_index=Words()))
        data = response.payload["data"]
        self.assertTrue(seen)
        sections = data["sections"]
        self.assertEqual([r["target_path"] for r in sections["unlinked_mentions"]],
                         ["Creatures/Aitrip.md"])
        self.assertEqual(sections["ambiguous_links"][0]["target"], "Twin")
        self.assertEqual(sections["name_collisions"][0]["name"], "Twin")
        self.assertEqual(data["counts"]["unlinked_mentions"], 1)
        self.assertEqual(data["counts"]["ambiguous_links"], 1)
        self.assertEqual(data["counts"]["name_collisions"], 1)

    def test_health_flags_common_single_word_names(self):
        os.makedirs(os.path.join(self.root, "Notes"))
        with open(os.path.join(self.root, "Notes", "Draft.md"), "w", encoding="utf8") as f:
            f.write("The tide rose near Water. We saw Water again, and then Hozon Keep fell. "
                    "Past Hozon Keep we met Hozon. We left Hozon alone near Water.\n")
        index = VaultIndex(self.vault, stat_interval=3600)

        class Files(FileManager):
            def get_words(self, path):
                return ["water", "keep"]

        class Words:
            def ensure_ready(self): pass
            def texts_for(self, word): return []
            def doc_count(self, word): return 0
        response = dispatch(self.request("GET", "/api/world/health", world_index=index,
                                         fm=Files(), word_index=Words()))
        rows = {row["phrase"]: row for row in
                response.payload["data"]["sections"]["names_without_entry"]}
        self.assertTrue(rows["Water"]["common"])
        self.assertFalse(rows["Hozon"]["common"])
        # A multi-word name never counts as common, even if each word is.
        self.assertFalse(rows["Hozon Keep"]["common"])
        self.assertEqual(rows["Water"]["triage"]["kind"], "name")
        self.assertIn("count", rows["Water"])

    def test_placement_route_contract_and_errors(self):
        os.makedirs(os.path.join(self.root, "Locations", "Biomes"))
        with open(os.path.join(self.root, "Locations", "Biomes", "Fenaya.md"), "w",
                  encoding="utf8") as f:
            f.write("Green valley biome.\n")
        with open(os.path.join(self.root, "Templates", "Person Template.md"), "w",
                  encoding="utf8") as f:
            f.write("## Facts\n")
        with open(os.path.join(self.root, "People", "Mira.md"), "w", encoding="utf8") as f:
            f.write("From: [[Locations/Biomes/Fenaya]]\n\nMira.\n")
        index = VaultIndex(self.vault, stat_interval=3600)

        def get(query):
            return dispatch(self.request("GET", "/api/world/placement", query,
                                         world_index=index))
        both = get({"from": "Locations/Biomes/Fenaya.md", "kind": "People"})
        self.assertEqual(both.status, 200)
        self.assertTrue(both.payload["ok"])
        self.assertEqual(both.payload["data"]["folder"], "People")
        self.assertEqual(both.payload["data"]["template"], "Templates/Person Template.md")
        self.assertEqual(both.payload["data"]["from_target"], "Locations/Biomes/Fenaya.md")
        self.assertIsNone(both.payload["data"]["suggested_kind"])
        self.assertEqual(set(both.payload["data"]),
                         {"kinds", "folder", "from_target", "template", "suggested_kind"})
        self.assertIn("People", both.payload["data"]["kinds"])
        only_from = get({"from": "Locations/Biomes/Fenaya.md"}).payload["data"]
        self.assertEqual(only_from["suggested_kind"], "People")
        self.assertIsNone(only_from["folder"])
        only_kind = get({"kind": "People"}).payload["data"]
        self.assertEqual((only_kind["folder"], only_kind["from_target"]), ("People", None))
        bare = get({})
        self.assertEqual(bare.status, 200)
        self.assertEqual(bare.payload["data"]["folder"], None)
        self.assertEqual(bare.payload["data"]["from_target"], None)
        self.assertEqual(bare.payload["data"]["template"], None)
        self.assertEqual(bare.payload["data"]["suggested_kind"], None)
        self.assertIn("People", bare.payload["data"]["kinds"])
        self.assertEqual(get({"kind": "Nonsense"}).status, 400)
        self.assertEqual(get({"kind": ["People"]}).status, 400)
        self.assertEqual(get({"from": "x" * 2000}).status, 400)
        self.assertEqual(get({"from": "Nowhere/Missing.md"}).status, 404)
        self.assertEqual(get({"from": "Nowhere/Missing.md", "kind": "People"}).status, 404)

    def test_matrix_route_includes_create_hints(self):
        os.makedirs(os.path.join(self.root, "Locations", "Biomes"))
        with open(os.path.join(self.root, "Locations", "Biomes", "Fenaya.md"), "w",
                  encoding="utf8") as f:
            f.write("Green valley biome.\n")
        with open(os.path.join(self.root, "Templates", "Person Template.md"), "w",
                  encoding="utf8") as f:
            f.write("## Facts\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        response = dispatch(self.request("GET", "/api/world/matrix", world_index=index))
        row = next(row for row in response.payload["data"]["rows"]
                   if row["path"] == "Locations/Biomes/Fenaya.md")
        self.assertEqual(row["cells"]["People"]["create"], {
            "folder": "People", "from_target": "Locations/Biomes/Fenaya.md",
            "template": "Templates/Person Template.md"})
        self.assertEqual(row["cells"]["Places"]["create"]["template"], None)

    def test_roll_route_excludes_non_world_notes_and_adds_from_targets(self):
        os.makedirs(os.path.join(self.root, "Locations", "Biomes"))
        with open(os.path.join(self.root, "Locations", "Biomes", "Fenaya.md"), "w",
                  encoding="utf8") as f:
            f.write("Green valley biome.\n")
        with open(os.path.join(self.root, "People", "Mira.md"), "w", encoding="utf8") as f:
            f.write("From: [[Locations/Biomes/Fenaya]]\n\nMira lives here.\n")
        os.makedirs(os.path.join(self.root, "Ideas"))
        with open(os.path.join(self.root, "Ideas", "List.md"), "w", encoding="utf8") as f:
            f.write("An idea.\n")
        with open(os.path.join(self.root, "How-To.md"), "w", encoding="utf8") as f:
            f.write("# Cheat Sheet\nMisconceptions\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        session = SimpleNamespace(active_words=lambda: ["showful", "arthrosporic"])
        seen = set()
        for _ in range(60):
            response = dispatch(self.request("POST", "/api/world/roll", world_index=index,
                                             session=session))
            self.assertEqual(response.status, 200)
            entry = response.payload["data"]["entry"]
            for card in (entry if isinstance(entry, list) else [entry]):
                seen.add(card["path"])
        self.assertTrue(seen)
        self.assertFalse({p for p in seen if p.startswith(("Templates/", "Ideas/"))
                          or p == "How-To.md"})
        response = dispatch(self.request("POST", "/api/world/roll",
                                         body={"entry": "People/Mira.md"},
                                         world_index=index, session=session))
        card = response.payload["data"]["entry"]
        self.assertEqual(card["biomes"], ["Locations/Biomes/Fenaya.md"])
        self.assertEqual(card["from_targets"], ["Locations/Biomes/Fenaya.md"])

    def test_graph_marks_story_folder_notes_as_not_world_entries(self):
        os.makedirs(os.path.join(self.root, "Story"))
        with open(os.path.join(self.root, "Story", "Scene.md"), "w", encoding="utf8") as f:
            f.write("The [[Mira]] scene.\n")
        index = VaultIndex(self.vault, stat_interval=3600, story_folders=["Story"])
        response = dispatch(self.request("GET", "/api/world/graph", world_index=index))
        nodes = {node["path"]: node for node in response.payload["data"]["nodes"]}
        self.assertFalse(nodes["Story/Scene.md"]["world"])
        self.assertTrue(nodes["People/Mira.md"]["world"])
        response = dispatch(self.request("GET", "/api/world/matrix", world_index=index))
        self.assertNotIn("Story", response.payload["data"]["kinds"])

    def test_roll_cards_link_by_title_unless_it_is_ambiguous(self):
        os.makedirs(os.path.join(self.root, "Flora and Fauna", "Forest-Jungle", "Hozon"))
        os.makedirs(os.path.join(self.root, "Cultures", "Elsewhere"))
        with open(os.path.join(self.root, "Flora and Fauna", "Forest-Jungle", "Hozon",
                               "Honestree.md"), "w", encoding="utf8") as f:
            f.write("A tree.\n")
        for folder in ("Cultures/Elsewhere", "Places"):
            with open(os.path.join(self.root, *folder.split("/"), "Twin.md"), "w",
                      encoding="utf8") as f:
                f.write("One of two.\n")
        with open(os.path.join(self.root, "How-To.md"), "w", encoding="utf8") as f:
            f.write("# Cheat Sheet\nMisconceptions\n")
        index = VaultIndex(self.vault, stat_interval=3600)
        session = SimpleNamespace(active_words=lambda: ["showful", "arthrosporic"])

        def link(path):
            response = dispatch(self.request("POST", "/api/world/roll", body={"entry": path},
                                             world_index=index, session=session))
            return response.payload["data"]["entry"]["link"]

        self.assertEqual(link("Flora and Fauna/Forest-Jungle/Hozon/Honestree.md"), "Honestree")
        self.assertEqual(link("Places/Twin.md"), "Places/Twin")
        self.assertEqual(link("Cultures/Elsewhere/Twin.md"), "Cultures/Elsewhere/Twin")


if __name__ == "__main__":
    unittest.main()
