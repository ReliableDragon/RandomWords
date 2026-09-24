from dataclasses import dataclass
import unittest

from entry import parse
from world_lexicon import WorldLexicon


@dataclass(frozen=True)
class Membership:
    path: str


class FakeVaultIndex:
    def __init__(self):
        self.entries = {
            "A.md": parse("Origin: alzarati\n\nAlzarati alzarati cats Unilux", "A.md"),
            "B.md": parse("Alzerati cat's Unilux unilux", "B.md"),
            "C.md": parse("ordinary daindowne", "C.md"),
        }
        self.memberships = {
            "A.md": (Membership("Biomes/Hot.md"),),
            "B.md": (Membership("Biomes/Cold.md"),),
            "C.md": (Membership("Biomes/Hot.md"),),
        }
        self.ready_calls = 0

    def ensure_ready(self):
        self.ready_calls += 1
        return True


class FakeFiles:
    def __init__(self):
        self.calls = 0

    def get_words(self, path):
        self.calls += 1
        assert path == "dicts/450k_words.txt"
        return ["ordinary"]


class FakeWordIndex:
    def __init__(self):
        self.ready_calls = 0

    def ensure_ready(self):
        self.ready_calls += 1

    def texts_for(self, word):
        return ["books/light.txt"] if word == "unilux" else []

    def doc_count(self, word):
        return len(self.texts_for(word))


class WorldLexiconTest(unittest.TestCase):
    def setUp(self):
        self.index = FakeVaultIndex()
        self.files = FakeFiles()

    def test_dictionary_subtraction_spellings_uses_biomes_and_which(self):
        words = FakeWordIndex()
        service = WorldLexicon(self.index, self.files, words)
        result = service.query()
        by_word = {row["word"]: row for row in result["entries"]}
        self.assertNotIn("ordinary", by_word)
        self.assertEqual(by_word["alzarati"]["spellings"], [
            {"spelling": "Alzarati", "count": 1},
            {"spelling": "alzarati", "count": 1},
        ])
        self.assertEqual(by_word["alzarati"]["uses"], [
            {"path": "A.md", "count": 2, "biomes": ["Biomes/Hot.md"]}
        ])
        self.assertEqual(by_word["unilux"]["count"], 3)
        self.assertEqual(by_word["unilux"]["which"],
                         {"count": 1, "texts": ["books/light.txt"]})
        service.query(q="uni")
        self.assertEqual(words.ready_calls, 1)
        self.assertEqual(self.files.calls, 1)

    def test_filters_query_biome_and_used_once(self):
        service = WorldLexicon(self.index, self.files)
        self.assertEqual([row["word"] for row in service.query(q="down")["entries"]],
                         ["daindowne"])
        hot = {row["word"] for row in service.query(biome="Biomes/Hot.md")["entries"]}
        self.assertIn("alzarati", hot)
        self.assertNotIn("alzerati", hot)
        once = {row["word"] for row in service.query(once=True)["entries"]}
        self.assertIn("alzarati", once)  # two uses, one note
        self.assertNotIn("unilux", once)

    def test_drift_points_rare_to_common_and_ignores_inflections(self):
        result = WorldLexicon(self.index, self.files).query()
        pairs = {(row["from"], row["to"]) for row in result["drift"]}
        self.assertIn(("alzerati", "alzarati"), pairs)
        self.assertNotIn(("cats", "cat's"), pairs)

    def test_searching_rare_spelling_keeps_full_vocabulary_drift_target(self):
        result = WorldLexicon(self.index, self.files).query(q="alzerati")
        self.assertEqual([row["word"] for row in result["entries"]], ["alzerati"])
        pair = next(row for row in result["drift"]
                    if row["from"] == "alzerati" and row["to"] == "alzarati")
        self.assertEqual(pair["from_paths"], ["B.md"])
        self.assertEqual(pair["to_paths"], ["A.md"])

    def test_nfc_casefold_combines_variants(self):
        self.index.entries = {
            "A.md": parse("Élan e\u0301lan ÉLAN", "A.md"),
        }
        self.index.memberships = {"A.md": ()}
        rows = WorldLexicon(self.index, self.files).query()["entries"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["word"], "élan")
        self.assertEqual(rows[0]["count"], 3)

    def test_drift_ignores_digits_and_equal_frequency_has_no_direction(self):
        self.index.entries = {
            "A.md": parse("1hp php php easten", "A.md"),
            "B.md": parse("easton", "B.md"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        result = WorldLexicon(self.index, self.files).query()
        words = {row["word"] for row in result["entries"]}
        self.assertIn("1hp", words)
        pairs = {(row["from"], row["to"]) for row in result["drift"]}
        self.assertNotIn(("1hp", "php"), pairs)
        self.assertNotIn(("easten", "easton"), pairs)
        self.assertNotIn(("easton", "easten"), pairs)


if __name__ == "__main__":
    unittest.main()
