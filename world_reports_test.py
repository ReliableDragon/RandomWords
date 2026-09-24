import os
import tempfile
import unittest

from vault import VaultManager
from vault_index import VaultIndex
from world_reports import coverage_matrix, health_report


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


if __name__ == "__main__":
    unittest.main()
