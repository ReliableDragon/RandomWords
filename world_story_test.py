import os
import tempfile
import unittest

from vault import VaultManager
from vault_index import VaultIndex
from world_story import export, parse_scene, quotes, report


class StoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        for folder in ("Story", "People", "Places", "Other"):
            os.makedirs(os.path.join(self.root, folder))
        self.write("People/Arin.md", "---\naliases: [de Relba, Arin de Relba]\n---\nArin writes.\n")
        self.write("Places/Fenaya.md", "A green valley.\n")
        self.write("Other/Fenaya.md", "A second place with the same title.\n")
        self.write("Story/02.md", "---\nwhen: 2\nwhere: \"[[Places/Fenaya]]\"\nwho:\n  - \"[[de Relba]]\"\n---\nArin reaches [[Places/Fenaya]].\n")
        self.write("Story/01.md", '---\naliases: Scene One\nwhen: 1\nwhere: "[[Places/Fenaya]]"\nwho: ["[[Artellus Poiné, Naturalist]]", "[[Dr. Otto Battar, Zoologist]]"]\n---\nThe valley is quiet.\n')
        self.write("Story/late.md", "---\nwhen: soon\n---\nArin waits.\n")
        self.write("Story/raw.md", "---\nwhen: 3\ncomplex: {not: supported}\n---\nArin speaks.\n")
        self.write("People/Quotes.md", "> The marsh remembers.\n> Its reeds do too.\n- [[de Relba]]\n")
        self.index = VaultIndex(VaultManager(self.root), stat_interval=3600,
                                story_folders=["Story"])
        self.index.ensure_ready()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        with open(os.path.join(self.root, *path.split("/")), "w", encoding="utf8") as output:
            output.write(text)

    def test_scene_order_and_metadata_are_separate_from_body_appearances(self):
        data = report(self.index, self.index.story_folders)
        self.assertEqual([row["path"] for row in data["scenes"]],
                         ["Story/01.md", "Story/02.md", "Story/late.md", "Story/raw.md"])
        first = data["scenes"][0]
        self.assertEqual(first["where"][0]["path"], "Places/Fenaya.md")
        self.assertEqual(len(first["who"]), 2)
        self.assertEqual(first["appearances"], [])
        second = data["scenes"][1]
        self.assertEqual({row["path"] for row in second["appearances"]},
                         {"People/Arin.md", "Places/Fenaya.md"})
        self.assertTrue(any("integer" in row["message"] for row in data["diagnostics"]))
        self.assertTrue(any("Unsupported" in row["message"] for row in data["diagnostics"]))
        appearance = next(row for row in data["appearances"] if row["path"] == "People/Arin.md")
        self.assertEqual(appearance["first_scene"], "Story/02.md")

    def test_limited_frontmatter_keeps_raw_unsupported_content_editable(self):
        raw = "---\nwhen: 1\nwhere:\n  - [[Fenaya]]\n---\nText\n"
        parsed = parse_scene(raw)
        self.assertEqual(parsed["when"], 1)
        self.assertEqual(parsed["where"], ["Fenaya"])
        flow = parse_scene('---\nwhen: 1\nwho: ["[[Artellus Poiné, Naturalist]]", "[[Dr. Otto Battar, Zoologist]]"]\n---\nText\n')
        self.assertEqual(flow["who"], ["Artellus Poiné, Naturalist", "Dr. Otto Battar, Zoologist"])
        unsupported = parse_scene("---\nwhen: 1\nwhere: {target: Fenaya}\n---\nText\n")
        self.assertEqual(unsupported["where"], [])
        self.assertIn("Unsupported", unsupported["diagnostics"][0])

    def test_quotes_filter_by_canonical_speaker_path(self):
        data = quotes(self.index, "People/Arin.md")
        self.assertEqual(data["quotes"][0]["path"], "People/Quotes.md")
        self.assertEqual(data["quotes"][0]["speaker"]["path"], "People/Arin.md")
        self.assertEqual(data["quotes"][0]["text"], "The marsh remembers.\nIts reeds do too.")
        with self.assertRaises(ValueError):
            quotes(self.index, "Arin")

    def test_export_has_safe_html_and_distinct_duplicate_title_anchors(self):
        self.write("Story/html.md", "---\nwhen: 4\n---\n<script>bad</script> [[Places/Fenaya]] [[Other/Fenaya]]\n")
        self.index.build()
        data = export(self.index, ["Story"], "story")
        html = data["html"]
        self.assertIn('id="glossary-Places%2FFenaya.md"', html)
        self.assertIn('id="glossary-Other%2FFenaya.md"', html)
        self.assertIn('href="#glossary-Places%2FFenaya.md"', html)
        self.assertIn("&lt;script&gt;bad&lt;/script&gt;", html)
        self.assertNotIn("<script>bad</script>", html)
        self.assertEqual(html.count('id="entry-Places%2FFenaya.md"'), 0)
        self.assertEqual(html.count('id="glossary-Places%2FFenaya.md"'), 1)
        self.assertIn("font:18px Georgia", html)

    def test_ambiguous_plain_names_do_not_become_two_appearances(self):
        self.write("Story/ambiguous.md", "---\nwhen: 5\n---\nFenaya is distant.\n")
        self.index.build()
        data = report(self.index, ["Story"])
        scene = next(row for row in data["scenes"] if row["path"] == "Story/ambiguous.md")
        self.assertEqual(scene["appearances"], [])
        self.assertIn("Ambiguous prose reference: Fenaya.", scene["diagnostics"])

    def test_story_folder_config_rejects_noncanonical_or_missing_directories(self):
        with self.assertRaises(ValueError):
            VaultIndex(VaultManager(self.root), story_folders=["../Story"])
        with self.assertRaises(ValueError):
            VaultIndex(VaultManager(self.root), story_folders=[".obsidian"])
        with self.assertRaises(ValueError):
            VaultIndex(VaultManager(self.root), story_folders=["Missing"])


if __name__ == "__main__":
    unittest.main()
