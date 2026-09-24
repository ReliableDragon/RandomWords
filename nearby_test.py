import os
import tempfile
import unittest

from entry import parse
from nearby import suggestions
from vault import VaultManager
from vault_index import VaultIndex


class NearbyTest(unittest.TestCase):
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

    def test_groups_spans_exclusions_and_revision(self):
        self.note("Locations/Biomes/Class/Fenaya.md")
        self.note("Creatures/Glow Fox.md", "---\naliases: Foxfire\n---\nFrom: [[Fenaya]]\n#bright #animal\n")
        self.note("Plants/Reed.md", "From: [[Fenaya]]\n#bright #plant\n")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        raw = ("---\naliases: Glow Fox\n---\nFrom: [[Fenaya]]\n#bright\n"
               "😀 Foxfire and [[Glow Fox]].\n```\nFoxfire\n```\n")
        draft = parse(raw, "Draft.md")
        groups = suggestions(draft, index, "draft-7")
        named = groups["named_not_linked"]
        self.assertEqual(len(named), 1)
        self.assertEqual(named[0]["expected"], "Foxfire")
        self.assertEqual(named[0]["link_target"], "Glow Fox")
        self.assertEqual(named[0]["client_revision"], "draft-7")
        self.assertEqual(named[0]["start"], len(raw[:raw.index("Foxfire")].encode("utf-16-le")) // 2)
        self.assertEqual({c["path"] for c in groups["same_biome"]},
                         {"Creatures/Glow Fox.md", "Plants/Reed.md"})
        self.assertEqual([c["path"] for c in groups["same_tags"]],
                         ["Creatures/Glow Fox.md", "Plants/Reed.md"])
        self.assertEqual(set(groups), {"named_not_linked", "same_biome", "same_tags"})

    def test_ambiguous_names_are_not_suggested(self):
        self.note("A/Wickrill.md")
        self.note("B/Wickrill.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        groups = suggestions(parse("Wickrill", "Draft.md"), index, "1")
        self.assertEqual(groups["named_not_linked"], [])

    def test_unique_alias_of_duplicate_title_uses_qualified_link_target(self):
        self.note("A/Wickrill.md", "---\naliases: First Wickrill\n---\n")
        self.note("B/Wickrill.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        named = suggestions(parse("First Wickrill", "Draft.md"), index, "2")["named_not_linked"]
        self.assertEqual(named[0]["link_target"], "A/Wickrill")

    def test_decomposed_text_before_match_does_not_shift_span(self):
        self.note("Alpha.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        raw = "Cafe\u0301 😀 Alpha"
        named = suggestions(parse(raw, "Draft.md"), index, 3)["named_not_linked"][0]
        self.assertEqual(named["expected"], "Alpha")
        self.assertEqual(named["start"], len("Cafe\u0301 😀 ".encode("utf-16-le")) // 2)

    def test_metadata_header_names_are_not_prose_mentions(self):
        self.note("Alpha.md", "---\naliases: Seedname\n---\n")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        raw = "Origin: Seedname\nThemes: Alpha\n\nNo mention in the prose."
        named = suggestions(parse(raw, "Draft.md"), index, "4")["named_not_linked"]
        self.assertEqual(named, [])


if __name__ == "__main__":
    unittest.main()
