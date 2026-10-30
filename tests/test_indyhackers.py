"""The Indianapolis board, which is the only source that knows where it is.

Measured 2026-09-11: of 5,009 stored postings exactly ONE is located in Indiana,
and 78 others match a naive "Indiana" search only because they are in India. The
34 ATS feeds are national tech companies; they are not a local instrument and no
reweighting can promote a local role that was never fetched.

IndyHackers runs PocketBase and serves its jobs collection as public read-only
JSON. Unlike an ATS board its records carry NO location field and NO url field —
the board is Indiana by charter, and that fact lives in the source rather than in
any posting. This adapter is where that fact is written down, so the rest of the
pipeline sees an ordinary row.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import ADAPTERS, indyhackers

# One record as the live API returns it, trimmed to the fields it actually has.
RECORD = {
    "id": "abc123",
    "company": "Opendate",
    "title": "Senior Full Stack Ruby on Rails Software Engineer",
    "description": "<p>Opendate is hiring in <strong>Indianapolis</strong>.</p>",
    "how_to_apply": '<p><a href="https://job-boards.greenhouse.io/opendate/jobs/1">Apply</a></p>',
    "salary_min": 130,
    "salary_max": 160,
    "approved": True,
    "filled": False,
    "created": "2026-07-02 14:27:02.837Z",
}

# What store.upsert_jobs names in its INSERT. A row missing one of these fails
# at the database, not in the adapter, which is a long way from the cause.
STORE_KEYS = {"id", "source", "company", "title", "location", "remote", "url",
              "description", "posted_at"}


def payload(*records):
    return {"page": 1, "perPage": 500, "totalItems": len(records),
            "totalPages": 1, "items": list(records)}


def one(**changes):
    """One row, from a record differing from the live shape only where stated."""
    return indyhackers.rows(payload({**RECORD, **changes}), "jobs")


class RowShapeTests(unittest.TestCase):
    def test_a_record_becomes_a_row_the_store_can_insert(self):
        rows = indyhackers.rows(payload(RECORD), "jobs")
        self.assertEqual(set(rows[0]), STORE_KEYS)

    def test_the_id_encodes_the_board_and_the_record(self):
        self.assertEqual(one()[0]["id"], "indyhackers:jobs:abc123")

    def test_the_board_is_reachable_by_the_name_a_profile_writes(self):
        self.assertIn("indyhackers", ADAPTERS)


class LocationTests(unittest.TestCase):
    """A record has no location field. The board's charter is the only source."""

    def test_a_city_named_in_the_description_becomes_the_location(self):
        self.assertEqual(one()[0]["location"], "Indianapolis, Indiana")

    def test_a_suburb_is_named_as_itself(self):
        row = one(description="<p>MISO is hiring an SDET in Carmel, Indiana.</p>")
        self.assertEqual(row[0]["location"], "Carmel, Indiana")

    def test_a_posting_naming_no_city_is_still_on_an_indiana_board(self):
        row = one(description="<p>We are hiring a backend engineer.</p>")
        self.assertEqual(row[0]["location"], "Indiana")


class ArrangementTests(unittest.TestCase):
    def test_a_remote_posting_is_marked_remote(self):
        self.assertEqual(one(description="<p>100% Remote - USA.</p>")[0]["remote"], 1)

    def test_a_hybrid_posting_is_not_remote(self):
        self.assertEqual(one(description="<p>Hybrid in Carmel.</p>")[0]["remote"], 0)

    def test_a_posting_saying_nothing_is_not_assumed_remote(self):
        self.assertEqual(one()[0]["remote"], 0)

    def test_a_distributed_system_does_not_make_a_posting_remote(self):
        # Measured on the live board: seven postings say "distributed logs",
        # "distributed resources" or "distributed systems". None is remote.
        row = one(description="<p>Resolve issues by reading distributed logs.</p>")
        self.assertEqual(row[0]["remote"], 0)

    def test_a_distributed_team_is_remote(self):
        row = one(description="<p>We are a fully distributed team.</p>")
        self.assertEqual(row[0]["remote"], 1)

    def test_a_posting_denying_it_is_remote_is_not_remote(self):
        row = one(description="<p>Onsite in Indianapolis, not hybrid or remote.</p>")
        self.assertEqual(row[0]["remote"], 0)


class ApplyLinkTests(unittest.TestCase):
    """29 of 41 live postings carry no link at all — most lead to the board."""

    def test_an_apply_link_is_where_the_posting_leads(self):
        self.assertEqual(one()[0]["url"], "https://job-boards.greenhouse.io/opendate/jobs/1")

    def test_a_posting_with_no_link_leads_to_the_board(self):
        self.assertEqual(one(how_to_apply="<p>DM me - @Matt Brown.</p>")[0]["url"],
                         indyhackers.BOARD)

    def test_an_email_address_is_not_somewhere_to_send_a_browser(self):
        row = one(how_to_apply='<p><a href="mailto:john@example.com">Email me</a></p>')
        self.assertEqual(row[0]["url"], indyhackers.BOARD)


class DescriptionTests(unittest.TestCase):
    """Scoring reads words. Markup reaching the scorer is noise it counts."""

    def test_tags_are_gone_from_the_description(self):
        # A tag becomes a space rather than nothing, which is why the full stop
        # detaches. The alternative runs the last word of one block into the
        # first of the next, inventing terms no posting contains.
        self.assertEqual(one()[0]["description"], "Opendate is hiring in Indianapolis .")

    def test_adjacent_blocks_do_not_run_their_words_together(self):
        row = one(description="<p>Senior Rails</p><p>Engineer</p>")
        self.assertEqual(row[0]["description"], "Senior Rails Engineer")

    def test_entities_become_ordinary_text(self):
        self.assertEqual(one(description="<p>Ruby&nbsp;&amp;&nbsp;Rails</p>")[0]["description"],
                         "Ruby & Rails")


class LivePostingsTests(unittest.TestCase):
    """The API filters these out, but a parser that trusts the query is one
    query-string edit away from emailing filled roles."""

    def test_a_filled_posting_is_not_returned(self):
        self.assertEqual(one(filled=True), [])

    def test_a_posting_awaiting_approval_is_not_returned(self):
        self.assertEqual(one(approved=False), [])
