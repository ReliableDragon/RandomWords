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
        return ["ordinary", "adulation"]


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
        drift = next(row for row in result["drift"]
                     if row["from"] == "alzerati" and row["to"] == "alzarati")
        self.assertEqual(drift["occurrences"], [{
            "path": "B.md", "revision": "", "spelling": "Alzerati",
            "replacement": "Alzarati",
            "line": 1, "context_before": "",
            "context_after": " cat's Unilux unilux",
            "start": 0, "end": 8,
        }])

    def test_occurrence_context_is_centered_and_truncated(self):
        prefix = "a" * 80 + " "
        suffix = " " + "z" * 80
        self.index.entries = {
            "A.md": parse("Alzarati alzarati", "A.md"),
            "B.md": parse(prefix + "Alzerati" + suffix, "B.md"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        drift = next(row for row in WorldLexicon(self.index, self.files).query()["drift"]
                     if row["from"] == "alzerati")
        occurrence = drift["occurrences"][0]
        self.assertEqual(len(occurrence["context_before"]), 61)
        self.assertTrue(occurrence["context_before"].startswith("…"))
        self.assertEqual(len(occurrence["context_after"]), 61)
        self.assertTrue(occurrence["context_after"].endswith("…"))

    def test_drift_suggestions_preserve_occurrence_case(self):
        self.index.entries = {
            "A.md": parse("alzarati alzarati alzarati alzarati", "A.md"),
            "B.md": parse("alzerati Alzerati ALZERATI", "B.md"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        drift = next(row for row in WorldLexicon(self.index, self.files).query()["drift"]
                     if row["from"] == "alzerati")
        self.assertEqual([row["replacement"] for row in drift["occurrences"]],
                         ["alzarati", "Alzarati", "ALZARATI"])

    def test_occurrence_offsets_are_textarea_utf16_offsets_after_headers(self):
        self.index.entries = {
            "A.md": parse("Origin: seed\n\nAlzarati alzarati", "A.md", "rev-a"),
            "B.md": parse("Origin: seed\n\n\U0001f30a Alzerati", "B.md", "rev-b"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        drift = next(row for row in WorldLexicon(self.index, self.files).query()["drift"]
                     if row["from"] == "alzerati")
        occurrence = drift["occurrences"][0]
        self.assertEqual(occurrence["path"], "B.md")
        self.assertEqual(occurrence["revision"], "rev-b")
        self.assertEqual(occurrence["line"], 3)
        raw = self.index.entries["B.md"].raw
        self.assertEqual(raw.encode("utf-16-le")[:occurrence["start"] * 2]
                         .decode("utf-16-le"), "Origin: seed\n\n\U0001f30a ")

    def test_occurrence_offsets_match_normalized_textarea_newlines(self):
        self.index.entries = {
            "A.md": parse("Alzarati alzarati", "A.md", "rev-a"),
            "B.md": parse("Origin: seed\r\n\r\nAlzerati", "B.md", "rev-b"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        drift = next(row for row in WorldLexicon(self.index, self.files).query()["drift"]
                     if row["from"] == "alzerati")
        occurrence = drift["occurrences"][0]
        editor_text = self.index.entries["B.md"].raw.replace("\r\n", "\n")
        self.assertEqual(editor_text[occurrence["start"]:occurrence["end"]], "Alzerati")

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

    def test_ignores_url_fragments_and_alphanumeric_tokens(self):
        self.index.entries = {
            "A.md": parse("1hp 40mph 4hhlgrb9qae3 https://example.test/Unilux", "A.md"),
        }
        self.index.memberships = {"A.md": ()}
        result = WorldLexicon(self.index, self.files).query()
        words = {row["word"] for row in result["entries"]}
        self.assertFalse({"1hp", "40mph", "4hhlgrb9qae3", "https", "example", "test", "unilux"} & words)

    def test_dictionary_inflections_are_not_coinages(self):
        self.index.entries = {"A.md": parse("adulation adulations", "A.md")}
        self.index.memberships = {"A.md": ()}
        words = {row["word"] for row in WorldLexicon(self.index, self.files).query()["entries"]}
        self.assertNotIn("adulations", words)

    def test_groups_novel_possessives_and_preserves_drift_replacements(self):
        self.index.entries = {
            "A.md": parse("Batter Batter Batter", "A.md"),
            "B.md": parse("Battar Battar's", "B.md"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        service = WorldLexicon(self.index, self.files)
        result = service.query(q="battar's")
        self.assertEqual([row["word"] for row in result["entries"]], ["battar"])
        entry = result["entries"][0]
        self.assertEqual(entry["count"], 2)
        self.assertEqual(entry["spellings"], [
            {"spelling": "Battar", "count": 1},
            {"spelling": "Battar's", "count": 1},
        ])
        drift = next(row for row in result["drift"]
                     if row["from"] == "battar" and row["to"] == "batter")
        self.assertEqual([row["replacement"] for row in drift["occurrences"]],
                         ["Batter", "Batter's"])

    def test_drift_ignores_equal_frequency_variants(self):
        self.index.entries = {
            "A.md": parse("easten", "A.md"),
            "B.md": parse("easton", "B.md"),
        }
        self.index.memberships = {"A.md": (), "B.md": ()}
        pairs = {(row["from"], row["to"])
                 for row in WorldLexicon(self.index, self.files).query()["drift"]}
        self.assertNotIn(("easten", "easton"), pairs)
        self.assertNotIn(("easton", "easten"), pairs)


if __name__ == "__main__":
    unittest.main()
