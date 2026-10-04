import os
import tempfile
import unittest
from types import SimpleNamespace

from entry import parse
from nearby import NameMatcher, suggest, suggestions, unlinked_mentions
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
        self.assertEqual(set(groups), {"named_not_linked", "same_biome", "same_tags",
                                       "talks_about_same_things",
                                       "linked_from_what_you_link"})

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

    def test_unlinked_overlap_sweep_preserves_order_and_boundaries(self):
        raw = "[[Alpha]]Beta Alpha Beta Gamma Delta Tie"
        matcher = NameMatcher([
            ("Alpha", "Alpha.md"),
            ("Beta", "Beta.md"),
            ("Alpha Beta", "Alpha Beta.md"),
            ("Beta Gamma Delta", "Beta Gamma Delta.md"),
            ("Tie", "First Tie.md"),
            ("Tie", "Second Tie.md"),
        ])
        index = SimpleNamespace(
            titles={
                "alpha": ("Alpha.md",), "beta": ("Beta.md",),
                "alpha beta": ("Alpha Beta.md",),
                "beta gamma delta": ("Beta Gamma Delta.md",),
                "tie": ("First Tie.md", "Second Tie.md"),
            },
            aliases={},
        )
        alpha_beta = raw.index("Alpha Beta")
        tie = raw.index("Tie")
        self.assertEqual(unlinked_mentions(raw, index, matcher), [
            (len("[[Alpha]]"), len("[[Alpha]]Beta"), "Beta.md"),
            (alpha_beta, alpha_beta + len("Alpha Beta"), "Alpha Beta.md"),
            (tie, tie + len("Tie"), "First Tie.md"),
        ])

        # A rejected longer candidate must not occupy the valid shorter span.
        invalid_first = SimpleNamespace(find=lambda _raw: [
            (0, len("Alpha Beta"), "Missing.md"),
            (0, len("Alpha"), "Alpha.md"),
        ])
        valid_only = SimpleNamespace(titles={"alpha": ("Alpha.md",)}, aliases={})
        self.assertEqual(unlinked_mentions("Alpha Beta", valid_only, invalid_first),
                         [(0, len("Alpha"), "Alpha.md")])

    def test_unclosed_links_and_fences_do_not_hide_a_later_name(self):
        raw = ("[[" * 2000) + "\n" + ("```x\n" * 2000) + "Alpha"
        matcher = NameMatcher([("Alpha", "Alpha.md")])
        index = SimpleNamespace(titles={"alpha": ("Alpha.md",)}, aliases={})
        start = raw.rindex("Alpha")
        self.assertEqual(unlinked_mentions(raw, index, matcher),
                         [(start, start + len("Alpha"), "Alpha.md")])

    def test_bm25_related_entries_skip_self_and_direct_links(self):
        self.note("Related.md", "Moon glass carries river light through the city.")
        self.note("Direct.md", "Moon glass and river light are common here.")
        self.note("Unrelated.md", "Distant legal customs govern inheritance.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        draft = parse("Moon glass casts river light. [[Direct]]", "Draft.md")
        cards = suggestions(draft, index, "5")["talks_about_same_things"]
        self.assertEqual([card["path"] for card in cards], ["Related.md"])
        self.assertIn("glass", cards[0]["shared_terms"])
        self.assertIn("river", cards[0]["reason"])

    def test_two_hop_uses_only_resolved_edges_and_handles_cycles(self):
        self.note("A.md", "[[B]] [[Draft]] [[Twin]]")
        self.note("B.md", "[[A]]")
        self.note("One/Twin.md")
        self.note("Two/Twin.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        draft = parse("[[A]]", "Draft.md")
        cards = suggestions(draft, index, "6")["linked_from_what_you_link"]
        self.assertEqual([card["path"] for card in cards], ["B.md"])
        self.assertEqual(cards[0]["reason"], "Linked from A")
        self.assertNotIn("Draft.md", [card["path"] for card in cards])

    def test_shared_settlement_is_called_out_without_becoming_a_biome(self):
        self.note("Locations/Biomes/Class/Fenaya.md")
        self.note("Locations/Settlements/Town.md", "From: [[Fenaya]]\n")
        self.note("People/Resident.md", "From: [[Town]]\n")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        draft = parse("From: [[Town]]\n\nA visitor arrives.", "Draft.md")
        cards = suggestions(draft, index, "7")["same_biome"]
        resident = next(card for card in cards if card["path"] == "People/Resident.md")
        self.assertEqual(resident["shared_direct_places"],
                         ["Locations/Settlements/Town.md"])
        self.assertIn("Shared place: Town", resident["reason"])
        self.assertIn("Shared biome: Fenaya", resident["reason"])
        self.assertNotIn("Locations/Settlements/Town.md",
                         {m.path for m in index.memberships["People/Resident.md"]})

    def merged_fixture(self):
        self.note("Locations/Biomes/Class/Fenaya.md", "Green valley.")
        self.note("Creatures/Glow Fox.md",
                  "---\naliases: Foxfire\n---\nFrom: [[Fenaya]]\n#bright #animal\nA lantern-tailed fox.")
        self.note("Plants/Reed.md", "From: [[Fenaya]]\n#bright #plant\nA tall reed.")
        self.note("People/Elsewhere.md", "From: [[Mountain]]\nSomeone far away.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        return index

    def test_cards_flag_places_and_namesakes(self):
        self.note("Locations/Places/Glade.md", "A clearing.")
        self.note("Creatures/Glade Fox.md", "#x")
        self.note("Other/Draft.md", "#x")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        draft = parse("Glade and Glade Fox. #x", "New/Draft.md")
        groups = suggestions(draft, index, "1")
        cards = {card["path"]: card for cards in groups.values() for card in cards}
        self.assertTrue(cards["Locations/Places/Glade.md"]["is_place"])
        self.assertFalse(cards["Creatures/Glade Fox.md"]["is_place"])
        self.assertTrue(cards["Other/Draft.md"]["namesake"])
        self.assertFalse(cards["Creatures/Glade Fox.md"]["namesake"])
        for group in groups.values():
            for card in group:
                self.assertIsInstance(card["is_place"], bool)
                self.assertIsInstance(card["namesake"], bool)

    def test_namesake_ignores_case_and_unicode_form_but_not_the_same_path(self):
        self.note("A/Cafe\u0301.md", "#x")
        self.note("Draft.md", "#x")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        groups = suggestions(parse("#x", "B/CAF\u00c9.md"), index, "1")
        by_path = {card["path"]: card for card in groups["same_tags"]}
        self.assertTrue(by_path["A/Cafe\u0301.md"]["namesake"])
        self.assertFalse(by_path["Draft.md"]["namesake"])
        same = suggestions(parse("#x", "Draft.md"), index, "1")
        self.assertNotIn("Draft.md", [c["path"] for c in same["same_tags"]])

    def test_merged_has_one_weighted_card_per_entry_and_leaves_groups_unchanged(self):
        index = self.merged_fixture()
        draft = parse("From: [[Fenaya]]\n#bright\nThe Foxfire lit the reeds. [[Reed]]", "Draft.md")
        result = suggest(draft, index, "rev-9")
        self.assertEqual(result["groups"], suggestions(draft, index, "rev-9"))
        merged = result["merged"]
        paths = [card["path"] for card in merged]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(paths[0], "Creatures/Glow Fox.md")
        fox = merged[0]
        by_group = {reason["group"]: reason for reason in fox["reasons"]}
        # "bright" also appears in both bodies, so the text group joins in.
        self.assertEqual(set(by_group), {"named_not_linked", "same_biome", "same_tags",
                                         "talks_about_same_things"})
        self.assertEqual(by_group["named_not_linked"]["weight"], 5.0)
        self.assertEqual(by_group["same_biome"]["weight"], 2.0)
        self.assertEqual(by_group["same_tags"]["weight"], 1.0)
        self.assertEqual(by_group["same_tags"]["shared_tags"], ["bright"])
        self.assertEqual(fox["score"], round(sum(r["weight"] for r in fox["reasons"]), 4))
        self.assertGreaterEqual(fox["score"], 8.0)
        named = by_group["named_not_linked"]
        self.assertEqual(named["text"], "Named as Foxfire")
        self.assertEqual(named["expected"], "Foxfire")
        self.assertEqual(named["link_target"], "Glow Fox")
        self.assertEqual(named["client_revision"], "rev-9")
        self.assertEqual(draft.raw[named["start"]:named["end"]], "Foxfire")
        self.assertEqual(named["occurrences"], 1)
        for key in ("title", "folder", "is_place", "namesake"):
            self.assertIn(key, fox)
        # Reed is linked directly, so it has no named or two-hop reason; the
        # biome and tag reasons still merge into one card.
        reed = next(card for card in merged if card["path"] == "Plants/Reed.md")
        self.assertEqual({r["group"] for r in reed["reasons"]}, {"same_biome", "same_tags"})
        self.assertLess(reed["score"], fox["score"])
        self.assertNotIn("People/Elsewhere.md", paths)

    def test_lowercase_named_matches_stay_linkable_but_weigh_less(self):
        self.note("Cosmology/Time.md", "---\naliases: Aeon\n---\nA god.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        draft = parse("Once upon a time the Aeon woke. Time passed.", "Draft.md")
        result = suggest(draft, index, "r1")
        named = result["groups"]["named_not_linked"]
        self.assertEqual([(c["expected"], c["exact_case"]) for c in named],
                         [("time", False), ("Aeon", True), ("Time", True)])
        reason = result["merged"][0]["reasons"][0]
        # The first exact-case mention represents the entry, at full weight.
        self.assertEqual((reason["expected"], reason["weight"], reason["occurrences"]),
                         ("Aeon", 5.0, 3))
        self.assertTrue(reason["exact_case"])
        self.assertEqual(reason["text"], "Named as Aeon")

        only = suggest(parse("Only a time, nothing else.", "Draft.md"), index, "r2")["merged"][0]
        reason = only["reasons"][0]
        self.assertEqual((reason["weight"], reason["text"], reason["exact_case"]),
                         (1.0, "Named as time (lowercase)", False))
        self.assertEqual(reason["link_target"], "Time")
        self.assertEqual("Only a time, nothing else."[reason["start"]:reason["end"]], "time")
        self.assertEqual(only["score"], 1.0)

    def test_merged_shared_place_adds_a_point_and_place_flag(self):
        self.note("Locations/Biomes/Class/Fenaya.md")
        self.note("Locations/Settlements/Town.md", "From: [[Fenaya]]\n")
        self.note("People/Resident.md", "From: [[Town]]\n")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        merged = suggest(parse("From: [[Town]]\n\nArrives.", "Draft.md"), index, "1")["merged"]
        resident = next(card for card in merged if card["path"] == "People/Resident.md")
        self.assertEqual(resident["reasons"][0]["weight"], 3.0)
        self.assertEqual(resident["reasons"][0]["shared_direct_places"],
                         ["Locations/Settlements/Town.md"])
        town = next(card for card in merged if card["path"] == "Locations/Settlements/Town.md")
        self.assertTrue(town["is_place"])

    def test_merged_scales_bm25_by_best_score_and_carries_two_hop_reason(self):
        self.note("Related.md", "Moon glass carries river light through the city.")
        self.note("Weaker.md", "River traffic and old customs, plus a long tail of other "
                  "unrelated words to lengthen this note considerably.")
        self.note("Hop.md", "Nothing relevant here.")
        self.note("Bridge.md", "[[Hop]]")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        draft = parse("Moon glass casts river light. [[Bridge]]", "Draft.md")
        merged = suggest(draft, index, "1")["merged"]
        related = next(card for card in merged if card["path"] == "Related.md")
        talks = related["reasons"][0]
        self.assertEqual(talks["group"], "talks_about_same_things")
        self.assertEqual(talks["weight"], 2.0)
        weaker = next(card for card in merged if card["path"] == "Weaker.md")
        self.assertLess(weaker["reasons"][0]["weight"], 2.0)
        self.assertGreater(weaker["reasons"][0]["weight"], 0.0)
        hop = next(card for card in merged if card["path"] == "Hop.md")
        self.assertEqual(hop["reasons"][0]["group"], "linked_from_what_you_link")
        self.assertEqual(hop["reasons"][0]["weight"], 1.5)
        self.assertEqual(hop["reasons"][0]["via"], ["Bridge.md"])

    def test_merged_orders_by_score_then_title_and_caps_at_twenty_five(self):
        for number in range(30):
            self.note(f"Things/Thing {number:02d}.md", "#shared\nBody.")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        merged = suggest(parse("#shared\nDraft.", "Draft.md"), index, "1")["merged"]
        self.assertEqual(len(merged), 25)
        self.assertEqual([card["title"] for card in merged],
                         [f"Thing {number:02d}" for number in range(25)])
        # The text group lists at most ten cards, so those score higher; within
        # equal scores title order decides.
        scores = [card["score"] for card in merged]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(set(scores), {2.0, 4.0})

    def test_merged_counts_repeat_mentions_once_using_the_first_span(self):
        self.note("Alpha.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        raw = "Alpha, then Alpha again."
        result = suggest(parse(raw, "Draft.md"), index, "1")
        self.assertEqual(len(result["groups"]["named_not_linked"]), 2)
        card = result["merged"][0]
        self.assertEqual(card["score"], 5.0)
        self.assertEqual(card["reasons"][0]["start"], 0)
        self.assertEqual(card["reasons"][0]["occurrences"], 2)

    def test_names_that_do_not_start_with_a_word_character_are_found(self):
        self.note("(Odd) Name.md")
        self.note("Ordinary.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        found = suggestions(parse("What is (Odd) Name and Ordinary?", "Draft.md"), index, "1")
        self.assertEqual({c["path"] for c in found["named_not_linked"]},
                         {"(Odd) Name.md", "Ordinary.md"})

    def test_names_without_a_letter_or_digit_are_never_matched(self):
        self.note("???.md")
        self.note("---.md", "---\naliases: \u2026\n---\n")
        self.note("Ordinary.md")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        found = suggest(parse("What is ??? and --- and \u2026 and Ordinary?", "Draft.md"),
                        index, "1")
        self.assertEqual([c["path"] for c in found["groups"]["named_not_linked"]],
                         ["Ordinary.md"])
        self.assertEqual([c["path"] for c in found["merged"]], ["Ordinary.md"])

    def test_suppressed_targets_are_not_offered_as_named_mentions(self):
        self.note("Time.md", "#x")
        self.note("Alpha.md", "#x")
        index = VaultIndex(self.vault)
        index.ensure_ready()
        result = suggest(parse("Time and Alpha. #x", "Draft.md"), index, "1",
                         frozenset({"Time.md"}))
        self.assertEqual([c["path"] for c in result["groups"]["named_not_linked"]],
                         ["Alpha.md"])
        time = next(c for c in result["merged"] if c["path"] == "Time.md")
        self.assertNotIn("named_not_linked", [r["group"] for r in time["reasons"]])
        self.assertLess(time["score"], 5.0)


if __name__ == "__main__":
    unittest.main()
