"""The Ashby board, read the way its API answers.

Ashby flags remote postings with isRemote, which the location text often does
not repeat. Location and description can both be null.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import ashby


def job(**changes):
    """One posting in the job-board API's shape, trimmed to the fields the adapter reads."""
    return {"id": "5f6e7d", "title": "Backend Engineer", "location": "Springfield",
            "isRemote": False, "jobUrl": "https://jobs.ashbyhq.com/wingtip/5f6e7d",
            "descriptionPlain": "Build services.", "publishedAt": "2026-10-01T12:00:00Z",
            **changes}


def fetch(*jobs):
    with mock.patch.object(ashby, "get_json", return_value={"jobs": list(jobs)}):
        return ashby.fetch("wingtip")


class AshbyTests(unittest.TestCase):
    def test_a_null_location_is_read_as_no_location(self):
        row = fetch(job(location=None))[0]
        self.assertEqual((row["location"], row["remote"]), ("", 0))

    def test_is_remote_marks_a_city_posting_remote(self):
        self.assertEqual(fetch(job(isRemote=True))[0]["remote"], 1)

    def test_a_null_description_is_read_as_empty(self):
        self.assertEqual(fetch(job(descriptionPlain=None))[0]["description"], "")


if __name__ == "__main__":
    unittest.main()
