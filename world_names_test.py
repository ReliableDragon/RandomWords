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

    def test_spans_are_in_editor_coordinates_for_crlf_text(self):
        raw = "First line here.\r\nSecond line.\r\n😀 The Shimmering Folk crossed.\r\n"
        rows = names_without_entries(FakeIndex({"Story.md": raw}))
        row = next(r for r in rows if r["phrase"] == "The Shimmering Folk")
        editor = raw.replace("\r\n", "\n").encode("utf-16-le")
        self.assertEqual(editor[row["start"] * 2:row["end"] * 2].decode("utf-16-le"),
                         "The Shimmering Folk")
        self.assertEqual(row["line"], 3)

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


    def test_linear_scanners_match_the_regular_expressions_they_replace(self):
        import random
        import re
        import world_names
        from world_spans import editor_offset, editor_offsets
        rng = random.Random(1)
        def sample(alphabet, length=14):
            return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, length)))
        wikilink = re.compile(r"\[\[[^\]]+\]\]")
        fence = re.compile(r"(?ms)^```.*?^```\s*$")
        def spans(matches):
            return [match.span() for match in matches]
        for _ in range(3000):
            text = sample(["[", "]", "[[", "]]", "a", "\n"])
            self.assertEqual(spans(world_names._WIKILINK.finditer(text)),
                             spans(wikilink.finditer(text)), text)
            text = sample(["```", "`", "\n", " ", "a", "base", "\r", "\n```\n"])
            self.assertEqual(list(world_names._fenced_block_spans(text)),
                             spans(fence.finditer(text)), text)
            text = sample(["a", "😀", "\r\n", "\r", "\n", " "])
            offsets = editor_offsets(text)
            for offset in range(len(text) + 1):
                self.assertEqual(offsets(offset), editor_offset(text, offset), text)
            text = sample(["Ab", " ", "\t", "\n", ". ", "?", "\u00a0", "x"])
            for start in range(len(text) + 1):
                prefix = text[:start].rstrip()
                expected = not prefix or prefix[-1] in ".!?" or "\n" in text[len(prefix):start]
                self.assertEqual(world_names._sentence_start(text, start), expected, text)

    def test_adversarial_notes_are_scanned_in_linear_time(self):
        import time
        size = 200_000
        # Unclosed links and fences, and many names on one line or many lines.
        for unit in ("[[", "```x\n", "Ab x ", "Ab x\n", "😀 Ab Cd\r\n"):
            with self.subTest(unit):
                index = FakeIndex({"Story.md": unit * (size // len(unit))})
                started = time.monotonic()
                names_without_entries(index)
                self.assertLess(time.monotonic() - started, 1.0)

if __name__ == "__main__":
    unittest.main()
