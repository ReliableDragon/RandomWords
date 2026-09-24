import os
import tempfile
import unittest

from vault import VaultManager
from vault_index import VaultIndex


class VaultIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.vault = VaultManager(self.temp.name, self.temp.name + "-recovery")

    def tearDown(self):
        self.temp.cleanup()

    def note(self, path, text=""):
        full = os.path.join(self.temp.name, *path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as output:
            output.write(text)

    def test_resolution_graph_backlinks_and_ambiguity(self):
        self.note("A/Wickrill.md", "same folder")
        self.note("B/Wickrill.md", "other")
        self.note("B/Stone.md", "---\naliases: Rock\n---\n")
        self.note("A/Source.md", "[[Wickrill]] [[Rock]] [[Missing]]")
        index = VaultIndex(self.vault, stat_interval=0)
        index.ensure_ready()
        self.assertEqual(index.resolve("Wickrill", "A/Source.md").path, "A/Wickrill.md")
        ambiguous = index.resolve("Wickrill", "C/Source.md")
        self.assertEqual(ambiguous.status, "ambiguous")
        self.assertEqual(set(ambiguous.candidates), {"A/Wickrill.md", "B/Wickrill.md"})
        self.assertEqual(index.resolve("B/Wickrill", "A/Source.md").path, "B/Wickrill.md")
        self.assertEqual(index.resolve("Rock").path, "B/Stone.md")
        self.assertEqual(index.forward_links["A/Source.md"][2].status, "unresolved")
        self.assertEqual(index.backlinks["A/Wickrill.md"][0][0], "A/Source.md")
        self.assertEqual(index.get_backlinks("A/Wickrill.md")[0]["target"], "Wickrill")

    def test_geography_multi_from_ancestry_and_declared_folder_fallback(self):
        self.note("Locations/Biomes/Class/Loaming Country.md")
        self.note("Locations/Biomes/Class/Fenaya.md")
        self.note("Locations/Places/Town.md", "From: [[Loaming Country]], [[Fenaya]]\n")
        self.note("People/Person.md", "From: [[Town]]\n")
        self.note("Cultures/Loaming Country/Custom.md")
        self.note("People/Loaming Country/Not Taxonomy.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        memberships = index.memberships["People/Person.md"]
        self.assertEqual([m.path for m in memberships], [
            "Locations/Biomes/Class/Loaming Country.md",
            "Locations/Biomes/Class/Fenaya.md",
        ])
        self.assertTrue(all(m.via == "ancestor_target" for m in memberships))
        self.assertEqual(index.memberships["Cultures/Loaming Country/Custom.md"][0].via,
                         "folder_fallback")
        self.assertEqual(index.memberships["People/Loaming Country/Not Taxonomy.md"], ())

    def test_tree_search_and_throttled_rebuild(self):
        self.note("A/Alpha.md", "A peculiar river")
        index = VaultIndex(self.vault, stat_interval=60)
        index.ensure_ready()
        self.assertEqual(index.tree()[0], {"path": "A", "name": "A", "type": "folder"})
        self.assertEqual(index.search("river")[0]["path"], "A/Alpha.md")
        self.note("B.md", "new")
        index.ensure_ready()
        self.assertNotIn("B.md", index.entries)
        index._last_stat = 0
        index.ensure_ready()
        self.assertIn("B.md", index.entries)

    def test_bm25_is_body_only_positive_and_deterministic(self):
        self.note("A.md", "Origin: moonstone\n\nriver glass river")
        self.note("B.md", "river glass")
        self.note("C.md", "forest medicine")
        self.note("Metadata.md", "Origin: moonstone\n\nplain body")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        rows = index.bm25("river glass")
        self.assertEqual([row[0] for row in rows[:2]], ["B.md", "A.md"])
        self.assertTrue(all(row[1] > 0 for row in rows))
        self.assertEqual(rows[0][2], ("glass", "river"))
        self.assertEqual(index.bm25("moonstone"), [])
        self.assertIn("forest", index.term_frequencies["C.md"])
        self.assertIn("medicine", index.term_frequencies["C.md"])

    def test_membership_provenance_is_immediate_place_and_deduplicates_biome(self):
        self.note("Locations/Biomes/Class/Fenaya.md")
        self.note("Locations/Settlements/Town.md", "From: [[Fenaya]]\n")
        self.note("People/Visitor.md", "From: [[Town]], [[Fenaya]]\n")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        memberships = index.memberships["People/Visitor.md"]
        self.assertEqual(len(memberships), 1)
        self.assertEqual(memberships[0].path, "Locations/Biomes/Class/Fenaya.md")
        self.assertEqual(memberships[0].via, "ancestor_target")
        self.assertEqual(memberships[0].source_path, "Locations/Settlements/Town.md")
        self.assertEqual(index.direct_places["People/Visitor.md"], (
            "Locations/Settlements/Town.md", "Locations/Biomes/Class/Fenaya.md"))


if __name__ == "__main__":
    unittest.main()
