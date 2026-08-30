"""Domestic relocation and an international move are different in kind.

score.py treated "Dublin, Ireland" exactly as "Denver, Colorado": both fell to
elsewhere_weight and collected 4.5 of 15 location points. The comment justifying
that says relocating is a tradeoff against comp rather than a hard no — true of a
domestic move, and false of one that needs a visa.

Eleven of the first twenty in the dry run were Dublin, London, São Paulo or
Toronto. Nothing is hard-excluded: some of these companies sponsor, and that is
his call. They simply must not outrank a domestic role by accident.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import location  # noqa: E402


class ClassifyTests(unittest.TestCase):
    def test_a_named_foreign_country_is_international(self):
        self.assertEqual(location.classify("Dublin, Ireland"), "international")

    def test_a_us_state_is_domestic(self):
        self.assertEqual(location.classify("Denver, Colorado"), "domestic")

    def test_a_us_state_abbreviation_is_domestic(self):
        self.assertEqual(location.classify("Menlo Park, CA"), "domestic")

    def test_united_states_spelled_out_is_domestic(self):
        self.assertEqual(location.classify("New York, New York, United States"), "domestic")

    def test_usa_is_domestic(self):
        self.assertEqual(location.classify("New York, New York, USA"), "domestic")

    def test_a_city_that_names_no_country_is_unknown_not_penalised(self):
        # Absence of evidence is not evidence of a visa problem.
        self.assertEqual(location.classify("In-Office"), "unknown")
        self.assertEqual(location.classify("Hybrid"), "unknown")

    def test_an_empty_location_is_unknown(self):
        self.assertEqual(location.classify(""), "unknown")
        self.assertEqual(location.classify(None), "unknown")

    def test_a_multi_city_list_with_any_us_option_is_domestic(self):
        # He can take the US office; the posting is reachable.
        self.assertEqual(location.classify("Dublin, Ireland; New York, NY"), "domestic")

    def test_a_multi_city_list_entirely_abroad_is_international(self):
        self.assertEqual(location.classify("Dublin, Ireland; London, England"), "international")

    def test_remote_alone_is_unknown_rather_than_assumed_domestic(self):
        self.assertEqual(location.classify("Remote"), "unknown")

    def test_a_country_name_inside_a_city_name_does_not_mislead(self):
        # "Toronto" contains no country; "Ontario" is not "Ireland".
        self.assertEqual(location.classify("Ontario, CA"), "domestic")

    def test_brazil_is_international(self):
        self.assertEqual(location.classify("São Paulo, São Paulo, Brazil"), "international")

    def test_canada_is_international(self):
        self.assertEqual(location.classify("Toronto, Canada"), "international")

    def test_england_is_international_even_without_the_uk(self):
        self.assertEqual(location.classify("London, England"), "international")


class NameTests(unittest.TestCase):
    def test_the_country_is_named_so_the_flag_is_readable(self):
        self.assertEqual(location.country("Dublin, Ireland"), "Ireland")

    def test_a_domestic_location_names_no_country(self):
        self.assertIsNone(location.country("Denver, Colorado"))


if __name__ == "__main__":
    unittest.main()


class ScoringTests(unittest.TestCase):
    """An international posting must not outrank a domestic one by accident."""

    def profile(self, **over):
        p = {"search": {"titles": [], "exclude_titles": [], "locations": ["Remote", "Indiana"],
                        "remote_only": False, "elsewhere_weight": 0.3},
             "skills": {}, "interests": {}, "dealbreakers": []}
        p["search"].update(over)
        return p

    def job(self, loc, remote=0):
        return {"id": "x", "title": "Backend Engineer", "description": "",
                "location": loc, "remote": remote}

    def test_an_international_posting_scores_below_a_domestic_one(self):
        from jobhunt import score
        _, dom = score.score(self.job("Denver, Colorado"), self.profile())
        _, intl = score.score(self.job("Dublin, Ireland"), self.profile())
        self.assertLess(intl["location"], dom["location"])

    def test_an_international_posting_is_not_excluded_outright(self):
        from jobhunt import score
        total, _ = score.score(self.job("Dublin, Ireland"), self.profile())
        self.assertGreaterEqual(total, 0)

    def test_an_unknown_location_is_treated_as_domestic_not_penalised(self):
        from jobhunt import score
        _, unknown = score.score(self.job("In-Office"), self.profile())
        _, dom = score.score(self.job("Denver, Colorado"), self.profile())
        self.assertEqual(unknown["location"], dom["location"])

    def test_a_remote_international_posting_is_still_marked_down(self):
        # "Remote, Ireland" is remote and still needs work authorisation.
        from jobhunt import score
        _, intl = score.score(self.job("Remote, Ireland", remote=1), self.profile())
        _, dom = score.score(self.job("Remote, Colorado", remote=1), self.profile())
        self.assertLess(intl["location"], dom["location"])

    def test_the_flag_names_the_country_so_he_can_judge_sponsorship(self):
        from jobhunt import gate
        labels = gate.flag_labels(self.job("Dublin, Ireland"))
        self.assertIn("Ireland", labels)

    def test_a_domestic_posting_carries_no_international_flag(self):
        from jobhunt import gate
        self.assertNotIn("international", gate.flag_labels(self.job("Denver, Colorado")))
