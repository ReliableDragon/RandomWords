import unittest

from entry import parse, render


class EntryTest(unittest.TestCase):
    def test_metadata_frontmatter_alias_forms_and_headers_are_lossless(self):
        raw = (
            "---\n"
            "aliases:\n"
            "  - Sightstone\n"
            "  - Unilux\n"
            "from: [[Loaming Country]]\n"
            "---\n"
            "From: [[Fenaya|Fenaya, too]]\n"
            "Origin: calothrix \\[freshwater algae\\] kallitype\n"
            "Themes: Heat, Sun\n"
            "A short body mentions [[Unilux#History|the stone]]. ${remember this} #loaming\n"
        )
        e = parse(raw, "Cultures/Loaming Country/The Fernlicht.md", "sha256:abc")
        self.assertEqual(e.raw, raw)
        self.assertEqual(e.revision, "sha256:abc")
        self.assertEqual(e.title, "The Fernlicht")
        self.assertEqual(e.kind, "Cultures")
        self.assertEqual(e.aliases, ["Sightstone", "Unilux"])
        self.assertEqual([l.target for l in e.from_targets], ["Loaming Country", "Fenaya"])
        self.assertEqual([l.display for l in e.from_targets], [None, "Fenaya, too"])
        self.assertTrue(all(l.span is not None for l in e.from_targets))
        self.assertEqual(e.origin, ["calothrix", "kallitype"])
        self.assertEqual(e.glosses, {"calothrix": "freshwater algae"})
        self.assertEqual(e.themes, ["Heat", "Sun"])
        self.assertEqual(e.tags, ["loaming"])
        self.assertEqual(e.notes, ["remember this"])
        link = next(link for link in e.links if link.target == "Unilux")
        self.assertEqual((link.target, link.heading, link.display), ("Unilux", "History", "the stone"))
        self.assertEqual(link.span.end - link.span.start, len("[[Unilux#History|the stone]]"))

    def test_scalar_and_inline_alias_lists(self):
        self.assertEqual(parse("---\naliases: Sightstone\n---\n", "A.md").aliases, ["Sightstone"])
        self.assertEqual(parse("---\naliases: [Sightstone, Unilux]\n---\n", "A.md").aliases,
                         ["Sightstone", "Unilux"])

    def test_utf16_spans_use_javascript_coordinates(self):
        text = "😀 before [[A]] and [[B|bee]]"
        e = parse(text, "A.md")
        self.assertEqual(e.links[0].span.start, len("😀 before ".encode("utf-16-le")) // 2)
        self.assertEqual(e.links[1].span.start, len("😀 before [[A]] and ".encode("utf-16-le")) // 2)

    def test_frontmatter_from_span_uses_its_actual_row_and_utf16_units(self):
        text = "---\ntitle: 😀\nfrom: [[Fenaya]]\naliases: [F]\n---\nBody\n"
        link = parse(text, "A.md").from_targets[0]
        start = len(text[:text.index("[[Fenaya]]")].encode("utf-16-le")) // 2
        self.assertEqual((link.span.start, link.span.end), (start, start + len("[[Fenaya]]")))

    def test_bom_frontmatter_and_parenthesized_origin_glosses(self):
        text = "\ufeff---\naliases: Sightstone\n---\nOrigin: calothrix (genus of freshwater cyanobacteria) kallitype (an early photograph) corespondency\n"
        e = parse(text, "The Fernlicht.md")
        self.assertEqual(e.aliases, ["Sightstone"])
        self.assertEqual(e.origin, ["calothrix", "kallitype", "corespondency"])
        self.assertEqual(e.glosses, {
            "calothrix": "genus of freshwater cyanobacteria",
            "kallitype": "an early photograph",
        })

    def test_fernlicht_origin_with_nested_parenthetical_gloss(self):
        raw = (
            "Origin: hamperedness (the state of being hampered (mis?)) "
            "kallitype (a process for making prints) "
            "corespondency (the act of corresponding)\n"
        )
        e = parse(raw, "Cultures/Loaming Country/The Fernlicht.md")
        self.assertEqual(e.origin, ["hamperedness", "kallitype", "corespondency"])
        self.assertEqual(e.glosses, {
            "hamperedness": "the state of being hampered (mis?)",
            "kallitype": "a process for making prints",
            "corespondency": "the act of corresponding",
        })

    def test_escaped_bracket_gloss_does_not_split_seed_words(self):
        e = parse(r"Origin: alpha \[a gloss with words\] beta" + "\n", "A.md")
        self.assertEqual(e.origin, ["alpha", "beta"])
        self.assertEqual(e.glosses, {"alpha": "a gloss with words"})

    def test_base_fence_is_preserved_as_escaped_code(self):
        e = parse("Before\n\n```base\nfile.links.contains(this.file.name)\n[[Should Not Link]] **plain** <tag>\n```\n\nAfter", "A.md")
        html = render(e, lambda target: "Target.md")
        self.assertIn("<pre><code>```base", html)
        self.assertIn("[[Should Not Link]] **plain** &lt;tag&gt;", html)
        self.assertNotIn("href=", html)
        self.assertIn("<p>After</p>", html)

    def test_word_count_and_stub(self):
        self.assertTrue(parse("From: [[X]]\n", "A.md").stub)
        body = " ".join("word%d" % n for n in range(25))
        e = parse(body, "A.md")
        self.assertEqual(e.words, 25)
        self.assertFalse(e.stub)

    def test_renderer_escapes_html_and_blocks_unsafe_urls(self):
        raw = '<script>alert(1)</script>\n\n[bad](javascript:alert(1)) https://good.test/x'
        html = render(parse(raw, "A.md"))
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('href="https://good.test/x"', html)

    def test_renderer_resolves_internal_links_through_callback(self):
        e = parse("See [[A/B|Bee]] and [[C#Heading]].", "A.md")
        html = render(e, lambda target: {"A/B": "Folder/A B.md", "C": "C.md"}.get(target))
        self.assertIn('/world/entry?path=Folder/A%20B.md', html)
        self.assertIn('href="/world/entry?path=C.md#Heading"', html)
        self.assertIn(">Bee</a>", html)


if __name__ == "__main__":
    unittest.main()
