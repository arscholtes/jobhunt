"""Per-company boilerplate detection.

Measured across the stored corpus, the repeated text usually sits at BOTH ends of
a posting and the tail is the larger half — gitlab 1,483 chars of shared prefix
against 3,708 of shared suffix, asana 2,014 of suffix against none at all. A
prefix-only stripper leaves most of the distortion in place.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import ClassVar

from jobhunt import culture, score

HEAD = "At ExampleCo we build with Ruby, Rails, Postgres, Kubernetes and Go. " * 4
TAIL = " ExampleCo is an equal opportunity employer. Benefits include Terraform training. " * 4


def rows(*bodies):
    return [{"description": b, "remote": 1, "location": "Remote", "title": "t"} for b in bodies]


class PrefixTests(unittest.TestCase):
    def test_the_shared_prefix_is_found(self):
        self.assertTrue(culture.boilerplate(rows(HEAD + "a", HEAD + "b", HEAD + "c")))

    def test_fewer_than_three_postings_is_not_enough_to_judge(self):
        self.assertEqual(culture.boilerplate(rows(HEAD + "a", HEAD + "b")), "")

    def test_a_short_shared_prefix_is_below_the_floor(self):
        self.assertEqual(culture.boilerplate(rows("Hi a", "Hi b", "Hi c")), "")

    def test_postings_with_nothing_in_common_yield_no_prefix(self):
        self.assertEqual(culture.boilerplate(rows("alpha", "beta", "gamma")), "")


class SuffixTests(unittest.TestCase):
    def test_the_shared_suffix_is_found(self):
        self.assertTrue(culture.boilerplate_suffix(rows("a" + TAIL, "b" + TAIL, "c" + TAIL)))

    def test_the_suffix_is_the_tail_not_the_head(self):
        found = culture.boilerplate_suffix(rows("a" + TAIL, "b" + TAIL, "c" + TAIL))
        self.assertTrue(TAIL.endswith(found))

    def test_fewer_than_three_postings_yields_no_suffix(self):
        self.assertEqual(culture.boilerplate_suffix(rows("a" + TAIL, "b" + TAIL)), "")

    def test_a_short_shared_suffix_is_below_the_floor(self):
        self.assertEqual(culture.boilerplate_suffix(rows("a x", "b x", "c x")), "")

    def test_identical_postings_do_not_collapse_to_the_whole_body(self):
        # Every character matches, so an unguarded scan would claim the entire
        # posting is boilerplate and leave nothing to score.
        same = HEAD + "body" + TAIL
        pre = culture.boilerplate(rows(same, same, same))
        suf = culture.boilerplate_suffix(rows(same, same, same))
        self.assertLess(len(pre) + len(suf), len(same))


class StrippingTests(unittest.TestCase):
    def test_both_ends_are_removed_leaving_the_role(self):
        body = HEAD + "The role: write Ruby all day." + TAIL
        out = score.strip_boilerplate(body, HEAD, TAIL)
        self.assertIn("write Ruby all day", out)
        self.assertNotIn("equal opportunity", out)
        self.assertNotIn("Kubernetes", out)

    def test_stripping_never_returns_empty_when_there_was_content(self):
        body = HEAD + TAIL
        self.assertIsInstance(score.strip_boilerplate(body, HEAD, TAIL), str)

    def test_overlapping_prefix_and_suffix_do_not_strip_past_each_other(self):
        body = "short"
        self.assertEqual(score.strip_boilerplate(body, "short", "short"), "")


if __name__ == "__main__":
    unittest.main()


class AssessTests(unittest.TestCase):
    """assess() must stay pure: the network answer is passed in, never fetched here."""

    PROFILE: ClassVar = {"culture": {"ships often": 5, "remote friendly": 3}}

    def corpus(self):
        return [{"description": HEAD + f"role {i}" + TAIL, "remote": 1,
                 "location": "Remote", "title": "Backend Engineer"} for i in range(4)]

    def term(self, result, name):
        return next(t for t in result["terms"] if t["term"] == name)

    def test_ships_often_reads_unknown_without_external_evidence(self):
        out = culture.assess(self.corpus(), self.PROFILE)
        self.assertIsNone(self.term(out, "ships often")["score"])

    def test_ships_often_is_scored_when_evidence_is_supplied(self):
        out = culture.assess(self.corpus(), self.PROFILE, ships_often=(0.8, "8/10 repos pushed in 30d"))
        self.assertEqual(self.term(out, "ships often")["score"], 0.8)

    def test_supplied_evidence_carries_its_source_into_the_report(self):
        out = culture.assess(self.corpus(), self.PROFILE, ships_often=(0.8, "8/10 repos pushed in 30d"))
        self.assertIn("repos pushed", self.term(out, "ships often")["why"])

    def test_answering_the_highest_weighted_term_raises_coverage(self):
        without = culture.assess(self.corpus(), self.PROFILE)
        with_ = culture.assess(self.corpus(), self.PROFILE, ships_often=(0.8, "why"))
        self.assertGreater(with_["covered"], without["covered"])

    def test_a_zero_cadence_is_scored_rather_than_treated_as_unknown(self):
        out = culture.assess(self.corpus(), self.PROFILE, ships_often=(0.0, "0/30 repos pushed in 30d"))
        self.assertEqual(self.term(out, "ships often")["score"], 0.0)

    def test_culture_never_reports_a_fit_score(self):
        # Culture is a separate axis, shown beside the fit score and never summed in.
        out = culture.assess(self.corpus(), self.PROFILE, ships_often=(0.8, "why"))
        self.assertNotIn("total", out)
        self.assertNotIn("fit", out)
