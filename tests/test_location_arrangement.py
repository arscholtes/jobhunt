"""Where a job is, and how it is worked, are two different questions.

classify() matched the location field as one string, so the word "Remote" sitting
beside a place name defeated it in both directions: "Argentina Remote" stopped
being international and "Remote U.S." stopped being domestic. Not misfiled —
unclassified, which is worse, because unknown is treated as domestic and carries
no flag.

Measured on live postings: of the top 100 scored, 31 were unknown, and
twelve of those are places he cannot work — including his single highest-scoring
posting at 96.7.

Remote is a work ARRANGEMENT. The place is the place. Parsed apart, "Argentina
Remote" is international and remote, "Remote U.S." is domestic and remote, and
one word can no longer break either.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import gate, location


class PlaceSurvivesArrangementTests(unittest.TestCase):
    def test_a_country_beside_remote_is_still_international(self):
        self.assertEqual(location.classify("Argentina Remote"), "international")

    def test_canada_beside_remote_is_still_international(self):
        self.assertEqual(location.classify("Canada Remote"), "international")

    def test_remote_before_the_us_is_still_domestic(self):
        self.assertEqual(location.classify("Remote U.S."), "domestic")

    def test_a_hyphenated_remote_us_is_domestic(self):
        self.assertEqual(location.classify("Remote - US"), "domestic")

    def test_a_hyphenated_remote_canada_is_international(self):
        self.assertEqual(location.classify("Remote - Canada"), "international")

    def test_a_parenthesised_province_list_is_still_international(self):
        self.assertEqual(
            location.classify("Canada - Remote (ON, AB, BC, or NS Only)"), "international")

    def test_a_multi_location_field_is_still_domestic(self):
        self.assertEqual(
            location.classify("San Francisco, CA | New York City, NY"), "domestic")

    def test_remote_with_no_place_stays_unknown(self):
        self.assertEqual(location.classify("Remote"), "unknown")

    def test_a_plain_place_is_unaffected(self):
        self.assertEqual(location.classify("Argentina"), "international")
        self.assertEqual(location.classify("San Francisco, CA"), "domestic")

    def test_hybrid_and_onsite_are_stripped_too(self):
        self.assertEqual(location.classify("Hybrid - Dublin, Ireland"), "international")
        self.assertEqual(location.classify("Onsite Denver, Colorado"), "domestic")

    def test_a_us_option_beside_a_foreign_one_is_reachable(self):
        # He can take the US office, so the posting is not blocked.
        self.assertEqual(location.classify("Remote (US or Canada)"), "domestic")

    def test_a_conjunction_is_not_read_as_oregon(self):
        # "or" is a US state abbreviation and also an English word; a named
        # country must not be overruled by it.
        self.assertEqual(location.classify("Canada - Remote (ON, AB, or NS)"), "international")


class ArrangementTests(unittest.TestCase):
    def test_remote_is_detected_independently_of_the_place(self):
        self.assertEqual(location.arrangement("Argentina Remote"), "remote")
        self.assertEqual(location.arrangement("Remote U.S."), "remote")

    def test_hybrid_is_detected(self):
        self.assertEqual(location.arrangement("Hybrid - Dublin, Ireland"), "hybrid")

    def test_onsite_is_detected(self):
        self.assertEqual(location.arrangement("In-Office"), "onsite")

    def test_a_plain_place_states_no_arrangement(self):
        self.assertIsNone(location.arrangement("San Francisco, CA"))

    def test_the_two_axes_are_independent(self):
        self.assertEqual(location.classify("Argentina Remote"), "international")
        self.assertEqual(location.arrangement("Argentina Remote"), "remote")


class ProseArrangementTests(unittest.TestCase):
    """A location field and a job description are different kinds of text.

    arrangement() reads a FIELD, where "distributed" can only describe the
    workforce. A description is prose, where it usually describes the system.
    Measured on the 41 live IndyHackers postings: seven say "distributed logs",
    "distributed resources" or "distributed systems", none of them remote, and
    one says outright that the role is "not hybrid or remote".
    """

    def test_distributed_logs_describe_a_system_not_a_workforce(self):
        self.assertFalse(location.remote_in_prose("Resolve issues by reading distributed logs."))

    def test_distributed_resources_on_a_power_grid_are_not_a_workplace(self):
        self.assertFalse(location.remote_in_prose("Digitalizing homes and distributed resources."))

    def test_a_distributed_team_is_a_workforce(self):
        self.assertTrue(location.remote_in_prose("We are a fully distributed team."))

    def test_plain_remote_is_still_remote(self):
        self.assertTrue(location.remote_in_prose("The setup: 100% remote, with an office."))

    def test_a_role_that_denies_being_remote_is_not_remote(self):
        self.assertFalse(location.remote_in_prose("Onsite in Indianapolis, not hybrid or remote."))

    def test_a_denial_does_not_silence_a_later_sentence(self):
        # The denial governs its own clause, not the whole posting.
        self.assertTrue(location.remote_in_prose(
            "Our support desk is not remote. This engineering role is 100% remote."))

    def test_prose_stating_nothing_is_not_remote(self):
        self.assertFalse(location.remote_in_prose("Senior Rails engineer for a growing team."))


class FlagMappingTests(unittest.TestCase):
    """A wrong flag that reads as reassurance is worse than no flag."""

    def flags(self, loc):
        return gate.flag_labels({"title": "Engineer", "description": "", "location": loc})

    def test_a_place_he_cannot_work_is_flagged(self):
        self.assertIn("international", self.flags("Argentina Remote"))

    def test_the_country_is_named_in_the_flag(self):
        self.assertIn("Argentina", self.flags("Argentina Remote"))

    def test_a_remote_us_role_carries_no_international_flag(self):
        self.assertNotIn("international", self.flags("Remote U.S."))

    def test_a_canadian_remote_role_is_flagged(self):
        self.assertIn("international", self.flags("Canada - Remote (ON, AB, BC, or NS Only)"))

    def test_a_domestic_office_carries_no_international_flag(self):
        self.assertNotIn("international", self.flags("San Francisco, CA"))


if __name__ == "__main__":
    unittest.main()
