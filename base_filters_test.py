import unittest

from base_filters import evaluate
from entry import parse, render


class BaseFilterTest(unittest.TestCase):
    def setUp(self):
        self.current = parse("", "Locations/Biomes/Loaming Country.md")
        self.entries = [
            parse("From: [[Loaming Country]]\n", "Settlements/Fenaya.md"),
            parse("From: [[Loaming Country]]\n", "Places/Old Well.md"),
            parse("From: [[Loaming Country]]\n", "Culture/The Fernlicht.md"),
            parse("From: [[Loaming Country]]\n", "Flora and Fauna/Marsh Heron.md"),
            parse("From: [[Other Biome]]\n", "Flora and Fauna/Other.md"),
            parse("From: [[Loaming Country]]\n", "Geonomy/Basalt.md"),
        ]

    def test_real_biome_template_nested_or_with_mixed_tabs(self):
        source = (
            "filters:\n"
            "  and:\n"
            "    - file.links.contains(this.file.name)\n"
            "    - or:\n"
            "      - file.path.contains(\"Settlements\")\n"
            "\t  - file.path.contains(\"Places\")\n"
        )
        result = evaluate(source, self.current, self.entries)
        self.assertTrue(result.supported)
        self.assertEqual(result.paths, ("Places/Old Well.md", "Settlements/Fenaya.md"))

    def test_template_path_filters_match_real_folder_names(self):
        source = 'filters:\n  and:\n    - file.links.contains(this.file.name)\n    - file.path.contains("Flora and Fauna")\n'
        result = evaluate(source, self.current, self.entries)
        self.assertTrue(result.supported)
        self.assertEqual(result.paths, ("Flora and Fauna/Marsh Heron.md",))

    def test_unrecognized_expression_is_not_partially_evaluated(self):
        source = 'filters:\n  and:\n    - file.links.contains(this.file.name)\n    - file.name.contains("Heron")\n'
        result = evaluate(source, self.current, self.entries)
        self.assertFalse(result.supported)
        self.assertEqual(result.paths, ())
        self.assertTrue(result.diagnostic)

    def test_qualified_links_use_canonical_resolution_when_available(self):
        duplicate = parse("From: [[Locations/Biomes/Loaming Country]]\n", "Things/Duplicate.md")
        source = "filters:\n  and:\n    - file.links.contains(this.file.name)\n"
        result = evaluate(source, self.current, [duplicate],
                          lambda target, _path: "Locations/Biomes/Another Country.md")
        self.assertEqual(result.paths, ())
        result = evaluate(source, self.current, [duplicate],
                          lambda target, _path: "Locations/Biomes/Loaming Country.md")
        self.assertEqual(result.paths, ("Things/Duplicate.md",))

    def test_render_shows_supported_results_and_unsupported_code_diagnostic(self):
        supported = "# Wildlife\n```base\nfilters:\n  and:\n    - file.links.contains(this.file.name)\n    - file.path.contains(\"Flora and Fauna\")\n``````\n"
        html = render(parse(supported, self.current.path), base_entries=self.entries)
        self.assertIn('class="base-results"', html)
        self.assertIn('path=Flora%20and%20Fauna/Marsh%20Heron.md', html)
        self.assertNotIn("<pre><code>", html)

        unsupported = "```base\nfilters:\n  and:\n    - file.name.contains(\"Heron\")\n```\n"
        html = render(parse(unsupported, self.current.path), base_entries=self.entries)
        self.assertIn('class="base-diagnostic"', html)
        self.assertIn("Unsupported Base filter expression", html)
        self.assertIn("file.name.contains", html)
        self.assertIn("<pre><code>", html)


if __name__ == "__main__":
    unittest.main()
