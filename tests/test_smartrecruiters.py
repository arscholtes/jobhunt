"""The SmartRecruiters board, read the way its API answers.

The list endpoint pages at 100 postings and carries no description, so each
posting costs a second call for its body. Several fields the adapter reads can
arrive as null rather than absent, and a default passed to .get() covers only an
absent key.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import smartrecruiters
from jobhunt.sources._http import FetchError


def summary(pid, **changes):
    """One posting from the list endpoint, trimmed to the fields the adapter reads."""
    return {"id": pid, "name": "Backend Engineer", "company": {"name": "Fabrikam"},
            "location": {"city": "Springfield", "region": "Exampleshire", "country": "zz",
                         "remote": False},
            "ref": f"https://api.smartrecruiters.com/v1/companies/fabrikam/postings/{pid}",
            "releasedDate": "2026-10-01T12:00:00.000Z", **changes}


def detail(**sections):
    return {"jobAd": {"sections": sections}}


class Board:
    """Answers list and detail URLs from canned pages, and records what was asked."""

    def __init__(self, pages, details=None):
        self.pages = pages
        self.details = details or {}
        self.listed = []

    def __call__(self, url):
        if "offset=" in url:
            offset = int(url.rsplit("offset=", 1)[1])
            self.listed.append(offset)
            return {"content": self.pages.get(offset, [])}
        pid = url.rsplit("/", 1)[1]
        return self.details.get(pid, detail(jobDescription={"text": "Build services."}))


def fetch(board):
    with mock.patch.object(smartrecruiters, "get_json", board):
        return smartrecruiters.fetch("fabrikam")


def one(posting, body=None):
    details = {posting["id"]: body} if body is not None else None
    return fetch(Board({0: [posting]}, details))[0]


class PaginationTests(unittest.TestCase):
    def test_every_page_below_the_cap_is_read(self):
        full = [summary(f"a{i}") for i in range(smartrecruiters.PAGE_SIZE)]
        rest = [summary(f"b{i}") for i in range(30)]
        rows = fetch(Board({0: full, 100: rest}))
        self.assertEqual(len(rows), 130)

    def test_a_short_page_is_taken_as_the_last(self):
        board = Board({0: [summary(f"a{i}") for i in range(30)]})
        fetch(board)
        self.assertEqual(board.listed, [0])

    def test_a_failed_list_call_raises_rather_than_returning_an_empty_board(self):
        # An empty result would read as "this company has no openings".
        with mock.patch.object(smartrecruiters, "get_json", side_effect=FetchError("HTTP 503")), \
             self.assertRaises(FetchError):
            smartrecruiters.fetch("fabrikam")


class NullFieldTests(unittest.TestCase):
    def test_a_null_location_is_read_as_no_location(self):
        row = one(summary("1", location=None))
        self.assertEqual((row["location"], row["remote"]), ("", 0))

    def test_a_null_company_falls_back_to_the_token(self):
        self.assertEqual(one(summary("1", company=None))["company"], "fabrikam")

    def test_a_null_ref_falls_back_to_the_public_posting_url(self):
        self.assertEqual(one(summary("1", ref=None))["url"],
                         "https://jobs.smartrecruiters.com/fabrikam/1")

    def test_a_null_section_leaves_the_others_readable(self):
        body = detail(companyDescription=None, jobDescription={"text": "Build   services."},
                      qualifications={"text": None})
        self.assertEqual(one(summary("1"), body)["description"], "Build services.")

    def test_a_null_job_ad_is_read_as_no_description(self):
        self.assertEqual(one(summary("1"), {"jobAd": None})["description"], "")


if __name__ == "__main__":
    unittest.main()
