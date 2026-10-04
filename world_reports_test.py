import os
import tempfile
import unittest
from unittest.mock import patch

from vault import VaultManager
from vault_index import VaultIndex
from world_reports import (coverage_matrix, health_report, mention_counts, placement,
                           unlinked_mention_rows)


class WorldReportsTest(unittest.TestCase):
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

    def test_matrix_deduplicates_multi_from_and_settlement_ancestry(self):
        biome = "Locations/Biomes/Grassland/Loaming Country.md"
        settlement = "Locations/Settlements/Old Ferry.md"
        self.note(biome, "A broad grassland region.")
        self.note("Locations/Biomes/Desert/Fenaya.md", "A dry region with dunes.")
        self.note(settlement, "From: [[Loaming Country]]\n\nA riverside village.")
        # Direct biome + settlement ancestry reaches the same canonical biome.
        self.note("Flora and Fauna/Animals/Loaming Country/Mayfly.md",
                  "From: [[Loaming Country]], [[Old Ferry]], [[Fenaya]]\n\n"
                  "A small creature that lives near the river in summer.")
        self.note("Ideas/Ideas.md", "Some backlog thought connected to this region.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        index.direct_places = {
            "Flora and Fauna/Animals/Loaming Country/Mayfly.md":
                (settlement,)
        }

        report = coverage_matrix(index)
        row = next(row for row in report["rows"] if row["path"] == biome)
        animals = row["cells"]["Flora and Fauna"]
        self.assertEqual(animals["count"], 1)
        self.assertEqual(animals["entries"][0]["path"],
                         "Flora and Fauna/Animals/Loaming Country/Mayfly.md")
        # Canonical biome and its settlement each occur once in Locations.
        locations = row["cells"]["Locations"]
        self.assertEqual({item["path"] for item in locations["entries"]},
                         {biome, settlement})
        mayfly_memberships = animals["entries"][0]["memberships"]
        self.assertEqual(len(mayfly_memberships), 1)
        self.assertEqual(animals["entries"][0]["direct_places"],
                         [{"path": settlement, "title": "Old Ferry"}])
        self.assertNotIn("Ideas", report["kinds"])

    def test_arbitrary_people_folder_does_not_infer_biome(self):
        biome = "Locations/Biomes/Grassland/Loaming Country.md"
        self.note(biome, "A region with hills, rivers, and grass.")
        person = "People/Loaming Country/River Guide.md"
        self.note(person, "A guide who knows every river and crossing here.")
        index = VaultIndex(self.vault)
        index.ensure_ready()

        report = coverage_matrix(index)
        row = report["rows"][0]
        self.assertEqual(row["cells"]["People"]["count"], 0)
        self.assertEqual(index.memberships[person], ())

    def test_health_sections_include_canonical_source_paths_and_aside_context(self):
        self.note("Cultures/Region/Small.md", "From: [[Missing Place]]\n\n"
                  "A short note. #rework\n${Should this custom survive winter?}")
        self.note("Cultures/Region/Connected.md",
                  "From: [[Missing Place]]\n\n"
                  "This entry has enough words to avoid being counted as a stub "
                  "while still linking to [[Small]].")
        self.note("Templates/Creature.md", "template scaffold")
        index = VaultIndex(self.vault)
        index.ensure_ready()

        report = health_report(index)
        source = "Cultures/Region/Small.md"
        self.assertIn(source, {row["path"] for row in report["stubs"]})
        self.assertIn(source, {row["path"] for row in report["rework"]})
        self.assertIn(source, {row["path"] for row in report["unresolved_links"]})
        aside = report["notes_to_self"][0]
        self.assertEqual(aside["path"], source)
        self.assertEqual(aside["text"], "Should this custom survive winter?")
        self.assertIn("#rework", aside["context"])
        self.assertEqual(aside["line"], 4)
        all_paths = {row["path"] for section in report.values() for row in section}
        self.assertNotIn("Templates/Creature.md", all_paths)
        self.assertEqual(report["names_without_entry"], [])
        self.assertEqual(report["spelling_drift"], [])

    def test_unresolved_link_rows_offer_the_source_notes_from_targets(self):
        place = "Locations/Places/Harbour.md"
        self.note(place, "A harbour where the ferries dock each evening.")
        source = "Cultures/Harbour/Ferrymen.md"
        self.note(source, "From: [[Harbour]]\n\nThey row out to meet the [[Tide Wyrm]].")
        index = VaultIndex(self.vault)
        index.ensure_ready()

        row = next(row for row in health_report(index)["unresolved_links"]
                   if row["target"] == "Tide Wyrm")
        self.assertEqual(row["from_targets"], [place])

    def test_unlinked_mentions_use_nearby_rules_and_carry_exact_spans(self):
        self.note("Creatures/Aitrip.md", "---\naliases: Airy\n---\nA drifting seed.")
        self.note("Creatures/Helay.md", "From: [[Aitrip]]\n\n😀 Helay meets an Aitrip "
                  "and later [[Aitrip]] again; see Airy.\n```\nAitrip\n```\n")
        self.note("Creatures/Other.md", "Origin: Aitrip\n\nNothing else here, only words.")
        self.note("Ideas/Idea.md", "Aitrip should be mentioned.")
        self.note("Templates/Template.md", "Aitrip in scaffolding.")
        self.note("Loose.md", "Aitrip in a loose root note.")
        self.note("A/Wickrill.md", "one")
        self.note("B/Wickrill.md", "two")
        self.note("Creatures/Uses Wickrill.md", "The Wickrill is ambiguous.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        rows = health_report(index)["unlinked_mentions"]
        self.assertEqual({(r["source_path"], r["target_path"], r["text"]) for r in rows},
                         {("Creatures/Helay.md", "Creatures/Aitrip.md", "Aitrip"),
                          ("Creatures/Helay.md", "Creatures/Aitrip.md", "Airy")})
        row = next(r for r in rows if r["text"] == "Aitrip")
        raw = index.entries["Creatures/Helay.md"].raw
        units = raw.encode("utf-16-le")
        self.assertEqual(units[row["start"] * 2:row["end"] * 2].decode("utf-16-le"), "Aitrip")
        self.assertEqual(row["line"], 3)
        self.assertIn("meets an Aitrip", row["context"])
        self.assertEqual(row["source_title"], "Helay")
        self.assertEqual(row["target_title"], "Aitrip")
        self.assertEqual(row["source_revision"], index.entries["Creatures/Helay.md"].revision)
        self.assertEqual(row["path"], "Creatures/Helay.md")
        self.assertTrue(row["already_linked"])
        self.assertTrue(row["exact_case"])

    def test_unlinked_mentions_skip_self_mentions_and_report_lowercase_words(self):
        self.note("Cosmology/Time.md", "Time is a god. Time watches.")
        self.note("Creatures/Clock.md", "It is about time and Time.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        rows = health_report(index)["unlinked_mentions"]
        self.assertEqual({r["source_path"] for r in rows}, {"Creatures/Clock.md"})
        self.assertEqual([(r["text"], r["exact_case"]) for r in rows],
                         [("time", False), ("Time", True)])

    def test_mention_counts_group_by_target_and_count_distinct_notes(self):
        self.note("Creatures/Aitrip.md", "A seed.")
        self.note("Creatures/One.md", "Aitrip and Aitrip.")
        self.note("Creatures/Two.md", "An Aitrip.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        counts = mention_counts(health_report(index)["unlinked_mentions"])
        self.assertEqual(counts, [{"target_path": "Creatures/Aitrip.md",
                                   "target_title": "Aitrip", "notes": 2, "mentions": 3}])

    def test_mention_spans_are_in_editor_coordinates_for_crlf_notes(self):
        self.note("Creatures/Aitrip.md", "A seed.")
        raw = "From: [[Somewhere]]\r\n\r\n😀 First line.\r\nAn Aitrip drifts.\r\nAnother Aitrip.\r\n"
        full = os.path.join(self.temp.name, "Creatures", "Helay.md")
        with open(full, "w", encoding="utf-8", newline="") as output:
            output.write(raw)
        index = VaultIndex(self.vault)
        index.ensure_ready()
        self.assertIn("\r\n", index.entries["Creatures/Helay.md"].raw)
        rows = health_report(index)["unlinked_mentions"]
        self.assertEqual(len(rows), 2)
        editor = raw.replace("\r\n", "\n")
        units = editor.encode("utf-16-le")
        for row in rows:
            self.assertEqual(units[row["start"] * 2:row["end"] * 2].decode("utf-16-le"), "Aitrip")
            self.assertEqual(row["text"], "Aitrip")
        self.assertEqual([row["line"] for row in rows], [4, 5])
        self.assertNotIn("\r", rows[0]["context"])

    def test_mention_enrichment_preserves_lf_spanning_bounds(self):
        target = "Creatures/Aitrip.md"
        source = "Creatures/Helay.md"
        raw = "😀 prefix Ai\r\ntrip suffix\rnext\nAfter."
        self.note(target, "A seed.")
        self.note(source, raw)
        index = VaultIndex(self.vault)
        index.ensure_ready()
        start = raw.index("Ai")
        end = raw.index(" suffix")

        def mentions(_raw, _index, _matcher, skip_path=None):
            return [(start, end, target)] if skip_path == source else []

        with patch("world_reports.find_unlinked_mentions", side_effect=mentions):
            rows = unlinked_mention_rows(index)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["text"], "Ai\r\ntrip")
        self.assertEqual(row["line"], 1)
        self.assertEqual(row["context"], "😀 prefix Ai\r\ntrip suffix\rnext")
        editor = raw.replace("\r\n", "\n").replace("\r", "\n").encode("utf-16-le")
        self.assertEqual(editor[row["start"] * 2:row["end"] * 2].decode("utf-16-le"),
                         "Ai\ntrip")

    def test_many_same_line_mentions_keep_bounded_context_and_exact_offsets(self):
        self.note("Creatures/Aitrip.md", "A seed.")
        raw = "😀 " + ("river " * 30) + ("Aitrip " * 1000) + ("marsh " * 30)
        self.note("Creatures/Many.md", raw)
        index = VaultIndex(self.vault)
        index.ensure_ready()
        rows = [row for row in unlinked_mention_rows(index)
                if row["source_path"] == "Creatures/Many.md"]
        self.assertEqual(len(rows), 1000)
        self.assertEqual({row["line"] for row in rows}, {1})
        self.assertTrue(rows[0]["context"].endswith("…"))
        self.assertTrue(rows[-1]["context"].startswith("…"))
        editor = raw.encode("utf-16-le")
        for row in (rows[0], rows[-1]):
            self.assertEqual(
                editor[row["start"] * 2:row["end"] * 2].decode("utf-16-le"),
                "Aitrip",
            )

    def test_mention_context_keeps_exact_radius_and_ellipsis_boundaries(self):
        self.note("Creatures/Aitrip.md", "A seed.")
        raw = ("." * 101) + "Aitrip" + ("," * 101)
        self.note("Creatures/Radius.md", raw)
        index = VaultIndex(self.vault)
        index.ensure_ready()
        row = next(row for row in unlinked_mention_rows(index)
                   if row["source_path"] == "Creatures/Radius.md")
        self.assertEqual(row["context"],
                         "…" + ("." * 100) + "Aitrip" + ("," * 100) + "…")

    def test_story_folder_notes_are_not_world_entries(self):
        self.note("Creatures/Aitrip.md", "A seed.")
        self.note("Story/Scene One.md", "The Aitrip was seen.")
        index = VaultIndex(self.vault, story_folders=["Story"])
        index.ensure_ready()
        self.assertEqual(coverage_matrix(index)["kinds"], ["Creatures"])
        self.assertEqual(health_report(index)["unlinked_mentions"], [])
        plain = VaultIndex(self.vault)
        plain.ensure_ready()
        self.assertEqual(coverage_matrix(plain)["kinds"], ["Creatures", "Story"])
        from world_reports import is_world_entry
        entry = index.entries["Story/Scene One.md"]
        self.assertTrue(is_world_entry("Story/Scene One.md", entry))
        self.assertFalse(is_world_entry("Story/Scene One.md", entry, ("Story",)))
        self.assertTrue(is_world_entry("Storytellers/Bard.md", entry, ("Story",)))

    def test_mention_scan_is_fast_on_a_few_hundred_notes(self):
        import time
        for number in range(300):
            self.note(f"Things/Thing {number}.md",
                      ("Thing %d meets Thing %d beside the river. " % (number, (number + 1) % 300))
                      + "Ordinary words fill the rest of this note. " * 40)
        index = VaultIndex(self.vault)
        index.ensure_ready()
        started = time.monotonic()
        rows = health_report(index)["unlinked_mentions"]
        self.assertLess(time.monotonic() - started, 5.0)
        self.assertGreaterEqual(len(rows), 300)

    def test_ambiguous_links_and_name_collisions(self):
        self.note("A/Wickrill.md", "---\naliases: Twin\n---\none")
        self.note("B/Wickrill.md", "two")
        self.note("C/Other.md", "[[Twin]] and [[Wickrill]]")
        self.note("D/Twin.md", "alias of another note's spelling")
        self.note("Templates/Twin.md", "scaffold")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        report = health_report(index)
        rows = report["ambiguous_links"]
        self.assertEqual([(r["source_path"], r["target"]) for r in rows],
                         [("C/Other.md", "Twin"), ("C/Other.md", "Wickrill")])
        self.assertEqual(rows[1]["candidates"], ["A/Wickrill.md", "B/Wickrill.md"])
        self.assertEqual(rows[1]["candidate_titles"], ["Wickrill", "Wickrill"])
        self.assertEqual(rows[1]["path"], "C/Other.md")
        collisions = {(r["kind"], r["name"].casefold()): r for r in report["name_collisions"]}
        wickrill = collisions[("name", "wickrill")]
        self.assertEqual(wickrill["paths"], ["A/Wickrill.md", "B/Wickrill.md"])
        self.assertEqual([m["via"] for m in wickrill["entries"]], ["title", "title"])
        twin = collisions[("name", "twin")]
        self.assertIn("A/Wickrill.md", twin["paths"])
        self.assertEqual({m["path"]: m["via"] for m in twin["entries"]}["A/Wickrill.md"], "alias")

    def test_matrix_cells_offer_create_hints(self):
        biome = "Locations/Biomes/Grass/Loaming Country.md"
        other = "Locations/Biomes/Desert/Fenaya.md"
        self.note(biome, "A region.")
        self.note(other, "Another region.")
        self.note("Flora and Fauna/Grassland/Loaming Country/Fox.md", "A fox.")
        self.note("Cultures/Loaming Country/Custom.md", "A custom.")
        self.note("Locations/Places/Glade.md", "From: [[Loaming Country]]\n\nA glade.")
        self.note("People/Mira.md", "From: [[Loaming Country]]\n\nA person.")
        self.note("Othernatural/Arts/Kinds/Thing.md", "An art.")
        self.note("Templates/Creature Template.md", "## Facts")
        self.note("Templates/Culture Template.md", "## Facts")
        self.note("Templates/Place Template.md", "## Facts")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        rows = {row["path"]: row for row in coverage_matrix(index)["rows"]}
        cells = rows[biome]["cells"]
        self.assertEqual(cells["Flora and Fauna"]["create"], {
            "folder": "Flora and Fauna/Grassland/Loaming Country", "from_target": biome,
            "template": "Templates/Creature Template.md"})
        self.assertEqual(cells["Cultures"]["create"], {
            "folder": "Cultures/Loaming Country", "from_target": biome,
            "template": "Templates/Culture Template.md"})
        self.assertEqual(cells["Locations"]["create"], {
            "folder": "Locations/Places", "from_target": biome,
            "template": "Templates/Place Template.md"})
        # No Person template exists, so none is offered; folders fall back to the kind.
        self.assertEqual(cells["People"]["create"], {
            "folder": "People", "from_target": biome, "template": None})
        self.assertEqual(cells["Othernatural"]["create"], {
            "folder": "Othernatural", "from_target": biome, "template": None})
        # A biome with no region folder falls back to the kind's top folder.
        empty = rows[other]["cells"]["Flora and Fauna"]
        self.assertEqual(empty["count"], 0)
        self.assertEqual(empty["create"], {
            "folder": "Flora and Fauna", "from_target": other,
            "template": "Templates/Creature Template.md"})
        # Existing fields are untouched.
        self.assertEqual(cells["Flora and Fauna"]["count"], 1)


    def placement_fixture(self):
        self.biome = "Locations/Biomes/Grass/Loaming Country.md"
        self.note(self.biome, "A region.")
        self.note("Flora and Fauna/Grassland/Loaming Country/Fox.md", "A fox.")
        self.note("Locations/Settlements/Old Ferry.md", "From: [[Loaming Country]]\n\nA town.")
        self.note("Locations/Places/Glade.md", "A glade with no region.")
        self.note("People/Mira.md", "From: [[Old Ferry]]\n\nA ferrier.")
        self.note("People/Joss.md", "From: [[Old Ferry]]\n\nA ferrier.")
        self.note("Cultures/Reed Folk.md", "From: [[Old Ferry]]\n\nA people.")
        self.note("Templates/Creature Template.md", "## Facts")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        return index

    def test_placement_resolves_a_settlement_to_its_regions_folder(self):
        index = self.placement_fixture()
        found = placement(index, "Locations/Settlements/Old Ferry.md", "Flora and Fauna")
        self.assertEqual(found["folder"], "Flora and Fauna/Grassland/Loaming Country")
        self.assertEqual(found["from_target"], "Locations/Settlements/Old Ferry.md")
        self.assertEqual(found["template"], "Templates/Creature Template.md")
        self.assertIsNone(found["suggested_kind"])
        self.assertEqual(found["kinds"], ["Cultures", "Flora and Fauna", "Locations", "People"])
        self.assertEqual(placement(index, self.biome, "Flora and Fauna")["folder"],
                         found["folder"])

    def test_placement_with_only_a_kind_or_an_unplaced_place_uses_defaults(self):
        index = self.placement_fixture()
        found = placement(index, None, "Locations")
        self.assertEqual((found["folder"], found["from_target"], found["suggested_kind"]),
                         ("Locations/Places", None, None))
        self.assertEqual(placement(index, None, "Flora and Fauna")["template"],
                         "Templates/Creature Template.md")
        glade = placement(index, "Locations/Places/Glade.md", "Flora and Fauna")
        self.assertEqual((glade["folder"], glade["from_target"]),
                         ("Flora and Fauna", "Locations/Places/Glade.md"))

    def test_placement_suggests_the_most_common_kind_only_without_a_kind(self):
        index = self.placement_fixture()
        found = placement(index, "Locations/Settlements/Old Ferry.md")
        self.assertEqual(found["suggested_kind"], "People")
        self.assertIsNone(found["folder"])
        self.assertIsNone(found["template"])
        self.assertIsNone(placement(index, "Locations/Places/Glade.md")["suggested_kind"])
        self.assertIsNone(placement(index, "Locations/Settlements/Old Ferry.md",
                                    "Cultures")["suggested_kind"])

    def test_aside_rows_match_the_per_aside_prefix_scan_they_replace(self):
        import random
        import re
        from entry import parse
        from world_reports import _aside_rows
        def expected(path, entry):
            rows = []
            for match in re.finditer(r"\$\{([^}]*)\}", entry.raw):
                line = entry.raw[:match.start()].count("\n") + 1
                lines = entry.raw.splitlines()
                start_line = end_line = line - 1
                while start_line > 0 and lines[start_line - 1].strip():
                    start_line -= 1
                while end_line + 1 < len(lines) and lines[end_line + 1].strip():
                    end_line += 1
                rows.append({"path": path, "title": entry.title, "text": match.group(1),
                             "context": "\n".join(lines[start_line:end_line + 1]).strip(),
                             "line": line})
            return rows
        rng = random.Random(1)
        for _ in range(3000):
            text = "".join(rng.choice(["$", "{", "}", "${", "a", " ", "\n", "\n\n", "\r", "\x0c"])
                           for _ in range(rng.randint(0, 20)))
            entry = parse(text, "Notes/A.md")
            self.assertEqual(_aside_rows(entry.path, entry), expected(entry.path, entry), text)

    def test_adversarial_asides_are_scanned_in_linear_time(self):
        import time
        from entry import parse
        from world_reports import _aside_rows
        size = 200_000
        for unit in ("${", "${x}", "${x}\n", "${x}\n\n"):
            with self.subTest(unit):
                entry = parse(unit * (size // len(unit)), "Notes/A.md")
                started = time.monotonic()
                _aside_rows(entry.path, entry)
                self.assertLess(time.monotonic() - started, 1.0)

if __name__ == "__main__":
    unittest.main()
