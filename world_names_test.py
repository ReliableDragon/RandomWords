import unittest

from entry import parse
from world_names import names_without_entries


class FakeIndex:
    def __init__(self, sources):
        self.entries = {path: parse(text, path) for path, text in sources.items()}
        self.titles = {entry.title.casefold(): (path,)
                       for path, entry in self.entries.items()}
        self.aliases = {"sightstone": ("Known.md",)}
        self.ready_calls = 0

    def ensure_ready(self):
        self.ready_calls += 1
        return True


class WorldNamesTest(unittest.TestCase):
    def test_finds_missing_multiword_name_with_context_and_utf16_span(self):
        raw = "😀 The Shimmering Folk crossed the marsh."
        rows = names_without_entries(FakeIndex({"Story.md": raw}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phrase"], "The Shimmering Folk")
        self.assertEqual(rows[0]["path"], "Story.md")
        self.assertEqual(rows[0]["line"], 1)
        self.assertEqual(rows[0]["context"], raw)
        self.assertEqual(rows[0]["start"], len("😀 ".encode("utf-16-le")) // 2)
        self.assertEqual(rows[0]["end"], rows[0]["start"] + len(
            "The Shimmering Folk".encode("utf-16-le")) // 2)

    def test_excludes_metadata_links_fences_tags_headings_and_known_names(self):
        raw = (
            "---\naliases: Front Matter Name\n---\n"
            "From: Header Country\nOrigin: Linked Seed\nThemes: Bright Theme\n\n"
            "# Heading Name\n"
            "Known appears with Sightstone and [[Linked Stranger]]. #TaggedName\n"
            "```\nFenced Stranger\n```\n"
        )
        rows = names_without_entries(FakeIndex({"Known.md": raw}))
        self.assertEqual(rows, [])

    def test_single_words_require_repetition_and_non_sentence_start_evidence(self):
        rows = names_without_entries(FakeIndex({
            "A.md": "Wanderers arrived. Wanderers stayed.",
            "B.md": "we greeted Hesper and later saw Hesper.",
        }))
        self.assertEqual([row["phrase"] for row in rows], ["Hesper"])
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["sources"], ["B.md"])

    def test_stable_order_and_templates_are_not_authored_notes(self):
        rows = names_without_entries(FakeIndex({
            "B.md": "Zither Guild met Alpha Circle.",
            "A.md": "Alpha Circle met Zither Guild.",
            "Templates/Entry.md": "Template Phantom belongs here.",
        }))
        self.assertEqual([(row["phrase"], row["path"]) for row in rows], [
            ("Alpha Circle", "A.md"),
            ("Zither Guild", "A.md"),
        ])
        self.assertTrue(all(row["count"] == 2 for row in rows))
        self.assertTrue(all(row["sources"] == ["A.md", "B.md"] for row in rows))

    def test_names_do_not_cross_lines_and_alphanumeric_ids_are_ignored(self):
        rows = names_without_entries(FakeIndex({
            "A.md": ("Abu Nuhas\n\nThemes return. ID 1DJ0rCQe6n repeats 1DJ0rCQe6n. "
                     "we Add and Add. we spoke After and After."),
        }))
        self.assertEqual([row["phrase"] for row in rows], ["Abu Nuhas"])

    def test_excludes_connective_prefixes_ideas_and_root_reference_notes(self):
        rows = names_without_entries(FakeIndex({
            "Places/Entry.md": ("After Jogar arrived. Although Lithoscarp remained. "
                                "All Biomes shifted. Shimmering Folk waited."),
            "Ideas/List.md": "Fate Foulers",
            "Overview.md": "Gelatinate Janitors",
        }))
        self.assertEqual([row["phrase"] for row in rows], ["Shimmering Folk"])


if __name__ == "__main__":
    unittest.main()
