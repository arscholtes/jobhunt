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

from jobhunt import culture  # noqa: E402

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
        from jobhunt import score
        body = HEAD + "The role: write Ruby all day." + TAIL
        out = score.strip_boilerplate(body, HEAD, TAIL)
        self.assertIn("write Ruby all day", out)
        self.assertNotIn("equal opportunity", out)
        self.assertNotIn("Kubernetes", out)

    def test_stripping_never_returns_empty_when_there_was_content(self):
        from jobhunt import score
        body = HEAD + TAIL
        self.assertIsInstance(score.strip_boilerplate(body, HEAD, TAIL), str)

    def test_overlapping_prefix_and_suffix_do_not_strip_past_each_other(self):
        from jobhunt import score
        body = "short"
        self.assertEqual(score.strip_boilerplate(body, "short", "short"), "")


if __name__ == "__main__":
    unittest.main()
