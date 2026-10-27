"""The Workable board, read the way its API answers.

Workable sends location as an object, and any of its parts can be null. A
default passed to .get() covers only an absent key, so a null that reached
.split() or .lower() would end the fetch run for every board after this one.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import workable


def job(**changes):
    """One posting in the widget API's shape, trimmed to the fields the adapter reads."""
    return {"id": "j-1", "shortcode": "ABC123", "title": "Backend Engineer",
            "location": {"city": "Springfield", "region": "Exampleshire", "country": "Freedonia",
                         "telecommuting": False},
            "url": "https://apply.workable.com/fabrikam/j/ABC123/",
            "description": "Build services.", "published_on": "2026-10-01", **changes}


def fetch(*jobs, name="Fabrikam"):
    with mock.patch.object(workable, "get_json", return_value={"name": name, "jobs": list(jobs)}):
        return workable.fetch("fabrikam")


class LocationTests(unittest.TestCase):
    def test_a_null_location_is_read_as_no_location(self):
        row = fetch(job(location=None))[0]
        self.assertEqual((row["location"], row["remote"]), ("", 0))

    def test_a_null_city_leaves_no_stray_separator(self):
        loc = {"city": None, "region": "Exampleshire", "country": "Freedonia"}
        self.assertEqual(fetch(job(location=loc))[0]["location"], "Exampleshire, Freedonia")

    def test_telecommuting_marks_a_posting_remote_whatever_the_city(self):
        loc = {"city": "Springfield", "telecommuting": True}
        self.assertEqual(fetch(job(location=loc))[0]["remote"], 1)


class NullFieldTests(unittest.TestCase):
    def test_a_null_shortcode_falls_back_to_the_id(self):
        self.assertEqual(fetch(job(shortcode=None))[0]["id"], "workable:fabrikam:j-1")

    def test_a_null_url_falls_back_to_the_application_url(self):
        row = fetch(job(url=None, application_url="https://apply.workable.com/fabrikam/j/ABC123/apply/"))[0]
        self.assertEqual(row["url"], "https://apply.workable.com/fabrikam/j/ABC123/apply/")

    def test_a_null_description_is_read_as_empty(self):
        self.assertEqual(fetch(job(description=None))[0]["description"], "")

    def test_a_null_account_name_falls_back_to_the_token(self):
        self.assertEqual(fetch(job(), name=None)[0]["company"], "fabrikam")


if __name__ == "__main__":
    unittest.main()
