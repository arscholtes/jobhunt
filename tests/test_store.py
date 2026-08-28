"""Persistence: the upsert, and the record that stops a posting being emailed twice."""

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import store  # noqa: E402


def job(jid="src:co:1", title="Backend Engineer"):
    return {"id": jid, "source": "src", "company": "co", "title": title,
            "location": "Remote", "remote": 1, "url": "http://x",
            "description": "d", "posted_at": None}


class UpsertTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)

    def tearDown(self):
        self.con.close()

    def test_a_new_posting_counts_as_new(self):
        self.assertEqual(store.upsert_jobs(self.con, [job()]), (1, 0))

    def test_a_known_posting_counts_as_seen_not_new(self):
        store.upsert_jobs(self.con, [job()])
        self.assertEqual(store.upsert_jobs(self.con, [job()]), (0, 1))

    def test_a_second_sighting_does_not_duplicate_the_row(self):
        store.upsert_jobs(self.con, [job()])
        store.upsert_jobs(self.con, [job()])
        self.assertEqual(self.con.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    def test_a_second_sighting_refreshes_last_seen(self):
        store.upsert_jobs(self.con, [job()])
        first = self.con.execute("SELECT last_seen FROM jobs").fetchone()[0]
        self.con.execute("UPDATE jobs SET last_seen = '2000-01-01'")
        store.upsert_jobs(self.con, [job()])
        self.assertNotEqual(self.con.execute("SELECT last_seen FROM jobs").fetchone()[0], "2000-01-01")
        self.assertIsNotNone(first)

    def test_an_unknown_status_is_refused_rather_than_stored(self):
        store.upsert_jobs(self.con, [job()])
        with self.assertRaises(ValueError):
            store.set_status(self.con, "src:co:1", "definitely-not-a-status")

    def test_a_known_status_is_stored(self):
        store.upsert_jobs(self.con, [job()])
        store.set_status(self.con, "src:co:1", "interested")
        self.assertEqual(
            self.con.execute("SELECT status FROM applications").fetchone()[0], "interested")

    def test_marking_notified_is_idempotent(self):
        store.upsert_jobs(self.con, [job()])
        store.mark_notified(self.con, ["src:co:1"])
        store.mark_notified(self.con, ["src:co:1"])
        self.assertEqual(self.con.execute("SELECT count(*) FROM notified").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
