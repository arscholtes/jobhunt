"""The digest: what gets emailed, once, and what it says about eligibility."""

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import notify, store  # noqa: E402


class DigestTestCase(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(store.SCHEMA)

    def tearDown(self):
        self.con.close()

    def add(self, jid, total, title="Backend Engineer", description="", company="co"):
        self.con.execute(
            """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                 description, posted_at, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (jid, "src", company, title, "Remote", 1, "http://x", description,
             None, "2026-01-01", "2026-01-01"))
        self.con.execute(
            "INSERT INTO scores (job_id, total, breakdown, scored_at) VALUES (?,?,?,?)",
            (jid, total, "{}", "2026-01-01"))
        self.con.commit()


class UnsentTests(DigestTestCase):
    def test_a_scored_posting_above_the_bar_is_unsent(self):
        self.add("a", 80)
        self.assertEqual([r["id"] for r in notify.unsent(self.con, min_score=60)], ["a"])

    def test_a_posting_below_the_bar_is_not_offered(self):
        self.add("a", 40)
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_a_notified_posting_is_never_offered_again(self):
        self.add("a", 80)
        store.mark_notified(self.con, ["a"])
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_highest_score_comes_first(self):
        self.add("low", 70)
        self.add("high", 90)
        self.assertEqual([r["id"] for r in notify.unsent(self.con, min_score=60)], ["high", "low"])

    def test_the_limit_caps_one_digest(self):
        for i in range(5):
            self.add(f"j{i}", 70 + i)
        self.assertEqual(len(notify.unsent(self.con, min_score=60, limit=2)), 2)

    def test_a_disqualified_posting_never_reaches_the_digest(self):
        self.add("a", -1)
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_marking_notified_twice_does_not_error(self):
        self.add("a", 80)
        store.mark_notified(self.con, ["a"])
        store.mark_notified(self.con, ["a"])
        self.assertEqual(notify.unsent(self.con, min_score=60), [])

    def test_the_send_record_is_what_gates_the_digest_not_a_time_window(self):
        # A missed run or a sleeping laptop must never drop a posting permanently.
        self.add("a", 80)
        self.assertEqual(len(notify.unsent(self.con, min_score=60)), 1)
        self.assertEqual(len(notify.unsent(self.con, min_score=60)), 1)


class TableTests(DigestTestCase):
    def test_the_table_renders_a_posting(self):
        self.add("a", 80, title="Backend Engineer")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertIn("Backend Engineer", html)

    def test_a_region_locked_posting_is_flagged_in_the_digest(self):
        self.add("a", 80, title="Forward Deployed Engineer - EMEA", description="EMEA only.")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertIn("region-locked", html)

    def test_a_clean_posting_carries_no_flag_noise(self):
        self.add("a", 80, title="Backend Engineer", description="Build things.")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertNotIn("region-locked", html)

    def test_a_flagged_posting_is_still_listed_never_hidden(self):
        self.add("a", 80, title="Forward Deployed Engineer - EMEA", description="EMEA only.")
        html = notify._table(notify.unsent(self.con, min_score=60))
        self.assertIn("Forward Deployed Engineer", html)


if __name__ == "__main__":
    unittest.main()
