"""profile.toml: what it must contain, and the defaults everything downstream reads.

score() and dealbreaker() index the search keys and optional sections directly,
with no fallback of their own. A profile holding only the three required sections
is valid, so load() has to fill in the rest or the first `jobhunt score` fails
with a KeyError.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import profile, score

MINIMAL = '[me]\nname = "Test Candidate"\n\n[search]\n\n[skills]\nruby = 5\n'


class LoadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "profile.toml"

    def tearDown(self):
        self._tmp.cleanup()

    def load(self, text):
        self.path.write_text(text)
        return profile.load(self.path)

    def test_a_missing_file_is_a_profile_error_naming_the_path(self):
        with self.assertRaises(profile.ProfileError) as caught:
            profile.load(self.path)
        self.assertIn(str(self.path), str(caught.exception))

    def test_a_missing_section_is_a_profile_error_naming_it(self):
        with self.assertRaises(profile.ProfileError) as caught:
            self.load('[me]\nname = "Test Candidate"\n\n[search]\n')
        self.assertIn("skills", str(caught.exception))

    def test_every_missing_section_is_named_at_once(self):
        with self.assertRaises(profile.ProfileError) as caught:
            self.load('[me]\nname = "Test Candidate"\n')
        self.assertIn("search, skills", str(caught.exception))

    def test_the_optional_sections_default_to_empty(self):
        p = self.load(MINIMAL)
        self.assertEqual((p["interests"], p["culture"], p["dealbreakers"], p["boards"]),
                         ({}, {}, [], []))

    def test_every_search_key_has_a_default(self):
        self.assertEqual(self.load(MINIMAL)["search"],
                         {"titles": [], "exclude_titles": [], "locations": [],
                          "remote_only": False, "min_score": 0})

    def test_a_value_the_profile_sets_is_kept(self):
        p = self.load(MINIMAL.replace("[search]\n", "[search]\nremote_only = true\nmin_score = 45\n"))
        self.assertEqual((p["search"]["remote_only"], p["search"]["min_score"]), (True, 45))

    def test_a_minimal_profile_can_be_scored(self):
        p = self.load(MINIMAL)
        job = {"id": "src:co:1", "title": "Backend Engineer", "description": "Ruby services.",
               "location": "Remote", "remote": 1, "company": "co"}
        self.assertIsNone(score.dealbreaker(job, p))
        total, _ = score.score(job, p)
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
