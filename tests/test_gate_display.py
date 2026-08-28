"""Eligibility flags have to be visible, or they are a silent filter by another name."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import gate  # noqa: E402


def job(title="Backend Engineer", description="", location="Remote", remote=1):
    return {"title": title, "description": description, "location": location,
            "remote": remote, "company": "co", "id": "src:co:1"}


class FlagLabelTests(unittest.TestCase):
    def test_a_clean_posting_has_no_labels(self):
        self.assertEqual(gate.flag_labels(job()), "")

    def test_a_region_locked_posting_is_labelled(self):
        j = job(title="Forward Deployed Engineer - EMEA", description="EMEA only.")
        self.assertIn("region", gate.flag_labels(j))

    def test_labels_are_short_enough_for_a_list_row(self):
        j = job(title="Forward Deployed Engineer - EMEA", description="EMEA only.")
        self.assertLessEqual(len(gate.flag_labels(j)), 40)

    def test_multiple_flags_are_all_shown(self):
        j = job(title="Staff Engineer - EMEA", description="EMEA only. Staff-level product engineer.")
        self.assertGreaterEqual(gate.flag_labels(j).count("·") + 1, 2)

    def test_a_degree_requirement_is_a_flag_and_never_a_filter(self):
        # Alex applies on experience with no completed degree, so degree language
        # is something he reads, not something that hides a posting from him.
        j = job(description="A Bachelor's degree is required for this role.")
        labels = gate.flag_labels(j)
        self.assertIn("degree", labels)

    def test_equivalent_experience_wording_is_distinguished_from_a_hard_requirement(self):
        hard = job(description="A Bachelor's degree is required.")
        soft = job(description="Bachelor's degree or equivalent practical experience.")
        self.assertNotEqual(gate.flag_labels(hard), gate.flag_labels(soft))

    def test_labels_never_raise_on_a_posting_with_no_description(self):
        self.assertIsInstance(gate.flag_labels(job(description=None)), str)


if __name__ == "__main__":
    unittest.main()
