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

    def skipped_render(self, body):
        skipped = []
        html = render(parse(body, "A.md"), skipped=skipped)
        return html, skipped

    def test_inline_code_is_escaped_and_not_interpreted(self):
        html, skipped = self.skipped_render("Use `<script>alert(1)</script>` and `[[Link]] **x**` here.")
        self.assertIn("<code>&lt;script&gt;alert(1)&lt;/script&gt;</code>", html)
        self.assertIn("<code>[[Link]] **x**</code>", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<strong>", html)
        self.assertEqual(skipped, [])

    def test_inline_code_with_double_backticks_and_attribute_breakout(self):
        html, _ = self.skipped_render('``a ` b`` and `"><img src=x onerror=alert(1)>`')
        self.assertIn("<code>a ` b</code>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)

    def test_ordered_lists_render_and_switch_from_bullets(self):
        html, _ = self.skipped_render("1. First\n2. Second <b>x</b>\n- bullet\n\n3. Third")
        self.assertIn("<ol>\n<li>First</li>\n<li>Second &lt;b&gt;x&lt;/b&gt;</li>\n</ol>", html)
        self.assertIn("<ul>\n<li>bullet</li>\n</ul>", html)
        self.assertIn('<ol start="3">', html)

    def test_horizontal_rules_do_not_become_bullets(self):
        for rule in ("---", "***", "___", "* * *", "- - -"):
            html, _ = self.skipped_render("above\n\n" + rule + "\n\nbelow")
            self.assertIn("<hr>", html, rule)
            self.assertNotIn("<li", html, rule)

    def test_tables_are_shown_as_escaped_raw_text_and_reported(self):
        html, skipped = self.skipped_render(
            "Intro\n\n| a | <script>x</script> |\n| --- | --- |\n| 1 | [[B]] |\n\nAfter")
        self.assertEqual(skipped, ["table"])
        self.assertIn('<div class="world-unsupported" data-kind="table">', html)
        self.assertIn("| a | &lt;script&gt;x&lt;/script&gt; |", html)
        self.assertIn("| 1 | [[B]] |", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<table", html)
        self.assertIn("<p>After</p>", html)

    def test_code_inside_link_labels_is_substituted_without_stray_placeholders(self):
        e = parse("[[Foo|the `code` label]] and [label `x`](https://example.com) "
                  "and [[Foo|`a` and `b`]]", "A.md")
        html = render(e, lambda target: "Foo.md")
        self.assertNotIn("\x00", html)
        self.assertIn(">the <code>code</code> label</a>", html)
        self.assertIn('rel="noopener noreferrer">label <code>x</code></a>', html)
        self.assertIn("<code>a</code> and <code>b</code>", html)

    def test_nested_placeholders_cannot_be_forged_or_injected(self):
        html, _ = self.skipped_render("`<img src=x onerror=alert(1)>` \x000\x00 \x0099\x00")
        self.assertNotIn("\x00", html)
        self.assertEqual(html.count("<code>"), 1)
        self.assertNotIn("<img", html)
        html, _ = self.skipped_render("[a `<script>x</script>`](javascript:alert(1)) "
                                      "[b `\"><b>`](https://ok.test)")
        self.assertNotIn("\x00", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn('href="javascript', html)
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_a_table_needs_two_header_cells_and_a_piped_separator(self):
        for source in ("a | b\n---", "| a |\n| --- |\n| 1 |", "a | b\n:---:\nrow"):
            html, skipped = self.skipped_render(source)
            self.assertEqual(skipped, [], source)
            self.assertNotIn("data-kind=\"table\"", html, source)
        html, skipped = self.skipped_render("a | b\n---\n\nabove\n\nx | y\n--- | ---\n1 | 2")
        self.assertEqual(skipped, ["table"])
        self.assertIn("<hr>", html)

    def test_pipes_without_a_separator_row_are_not_a_table(self):
        html, skipped = self.skipped_render("a | b\n---\nplain")
        self.assertEqual(skipped, [])
        self.assertNotIn("world-unsupported", html)

    def test_images_are_inert_and_reported_including_unsafe_urls(self):
        html, skipped = self.skipped_render(
            '![alt <b>](javascript:alert(1)) and ![](https://ok.test/a.png "t")')
        self.assertEqual(skipped, ["image"])
        self.assertEqual(html.count('data-kind="image"'), 2)
        self.assertNotIn("<img", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("href=", html)
        self.assertIn("![alt &lt;b&gt;](javascript:alert(1))", html)

    def test_embeds_are_inert_and_reported(self):
        html, skipped = self.skipped_render("![[Picture.png]] and ![[<img src=x onerror=alert(1)>]]")
        self.assertEqual(skipped, ["embed"])
        self.assertEqual(html.count('data-kind="embed"'), 2)
        self.assertNotIn("<img", html)
        self.assertNotIn("<a ", html)
        self.assertIn("![[Picture.png]]", html)

    def test_task_checkboxes_are_kept_as_text_and_reported(self):
        html, skipped = self.skipped_render("- [ ] write <i>it</i>\n- [x] done\n1. [X] numbered\n- [link](https://ok.test/)")
        self.assertEqual(skipped, ["task"])
        self.assertEqual(html.count('data-kind="task"'), 3)
        self.assertIn('<span class="world-unsupported" data-kind="task">[ ]</span> write &lt;i&gt;it&lt;/i&gt;', html)
        self.assertNotIn("<input", html)
        self.assertIn('href="https://ok.test/"', html)

    def test_skipped_lists_each_kind_once_in_first_seen_order(self):
        _, skipped = self.skipped_render("![[A]] ![[B]]\n\n![i](x) - not a task\n\n- [ ] t\n- [ ] u")
        self.assertEqual(skipped, ["embed", "image", "task"])

    def test_unmatched_and_many_backtick_runs_render_quickly(self):
        import time
        started = time.monotonic()
        html, _ = self.skipped_render("`a" * 50000 + " ``b` " * 20000)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertIn("<code>", html)

    def test_adversarial_unclosed_constructs_parse_and_render_in_linear_time(self):
        import time
        size = 200_000
        units = ["[[", "![[", "[", "](", "[a](", "![", "![a](", "${", "`", "x`` ", "```a\n", "[[\n"]
        cases = {repr(unit): (unit * (size // len(unit) + 1))[:size] for unit in units}
        # A table header over a separator row of long whitespace runs.
        cases["table spaces"] = "a|b\n" + " " * (size // 2) + "|" + " " * (size // 2) + "x"
        cases["table trailing spaces"] = "a|b\n|-" + " " * size + "x"
        for name, text in cases.items():
            with self.subTest(name):
                started = time.monotonic()
                render(parse(text, "A.md"), lambda target: "A.md")
                self.assertLess(time.monotonic() - started, 1.0)

    def test_linear_scanners_match_the_regular_expressions_they_replace(self):
        import random
        import re
        import entry
        rng = random.Random(1)
        def sample(alphabet):
            return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14)))
        for scanned, alphabet in ((entry._WIKILINK, ["[", "]", "[[", "]]", "a", "\n"]),
                                  (entry._ASIDE, ["$", "{", "}", "${", "a", "\n"]),
                                  (entry._MARKDOWN_LINK, ["[", "]", "(", ")", "](", "a"])):
            for _ in range(3000):
                text = sample(alphabet)
                self.assertEqual([(m.span(), m.groups()) for m in scanned.finditer(text)],
                                 [(m.span(), m.groups()) for m in scanned.pattern.finditer(text)], text)
        fence = re.compile(r"(?ms)^```(?:base)?\s*.*?^```\s*$")
        for _ in range(3000):
            text = sample(["```", "`", "\n", " ", "a", "base", "\r"])
            self.assertEqual(entry._without_fenced_blocks(text), fence.sub(" ", text), text)
        separator = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
        for _ in range(3000):
            text = sample(["|", "-", ":", " ", "x"])
            self.assertEqual(bool(entry._TABLE_SEPARATOR.match(text)), bool(separator.match(text)), text)

    def test_utf16_offsets_match_encoding_the_prefix(self):
        import random
        import entry
        rng = random.Random(1)
        for _ in range(3000):
            text = "".join(rng.choice(["a", "😀", "é", "\n", "𝔸", "[[a]]"])
                           for _ in range(rng.randint(0, 12)))
            utf16 = entry._utf16_offsets(text)
            for offset in range(len(text) + 1):
                self.assertEqual(utf16(offset), len(text[:offset].encode("utf-16-le")) // 2, text)

    def test_many_links_after_astral_characters_parse_in_linear_time(self):
        import time
        size = 200_000
        for unit in ("[[a]] ", "😀 [[a]] "):
            with self.subTest(unit):
                text = unit * (size // len(unit))
                started = time.monotonic()
                links = parse(text, "A.md").links
                self.assertLess(time.monotonic() - started, 1.0)
                last = text.rindex("[[a]]")
                self.assertEqual(links[-1].span.start, len(text[:last].encode("utf-16-le")) // 2)

    def test_render_without_skipped_argument_is_unchanged(self):
        self.assertIn("world-unsupported", render(parse("![[A]]", "A.md")))


if __name__ == "__main__":
    unittest.main()
