"""The Lever board, read the way its API answers.

Lever nests location and commitment under `categories`, and either level can be
null. Remote is not always in the location text: a posting can say so only in
its workplaceType.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import lever


def job(**changes):
    """One posting in the postings API's shape, trimmed to the fields the adapter reads."""
    return {"id": "0a1b2c", "text": "Backend Engineer",
            "categories": {"location": "Springfield", "commitment": "Full-time"},
            "workplaceType": "onsite",
            "hostedUrl": "https://jobs.lever.co/tailspin/0a1b2c",
            "descriptionPlain": "Build services.", **changes}


def fetch(*jobs):
    with mock.patch.object(lever, "get_json", return_value=list(jobs)):
        return lever.fetch("tailspin")


class LeverTests(unittest.TestCase):
    def test_null_categories_are_read_as_no_location(self):
        row = fetch(job(categories=None))[0]
        self.assertEqual((row["location"], row["remote"]), ("", 0))

    def test_a_remote_workplace_type_marks_a_city_posting_remote(self):
        self.assertEqual(fetch(job(workplaceType="remote"))[0]["remote"], 1)

    def test_a_null_commitment_and_workplace_type_are_not_remote(self):
        row = fetch(job(categories={"location": "Springfield", "commitment": None},
                        workplaceType=None))[0]
        self.assertEqual(row["remote"], 0)

    def test_a_null_description_is_read_as_empty(self):
        self.assertEqual(fetch(job(descriptionPlain=None))[0]["description"], "")


if __name__ == "__main__":
    unittest.main()
