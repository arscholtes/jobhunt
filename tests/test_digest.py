"""What goes in the daily digest, and what the application pipeline is doing.

The threshold is the interesting part. An absolute bar was silently invalidated
by a scoring improvement: stripping boilerplate lowered every score, and the top
withheld posting missed a bar of 60 by 0.2 points. Nothing reported that the
constant had stopped meaning what it meant when it was written.

So the gate is a percentile of the scored postings — it moves when scoring moves —
and the volume is a rank cap, because what a reader wants is the best few they
have not seen, not everything above a number.
"""

import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import digest, store


def scores(*values):
    return list(values)


class ThresholdTests(unittest.TestCase):
    def test_the_bar_is_derived_from_the_postings_not_a_constant(self):
        low = digest.percentile_bar(scores(*range(0, 100)), 0.90)
        high = digest.percentile_bar(scores(*range(100, 200)), 0.90)
        self.assertLess(low, high)

    def test_a_uniform_shift_downward_moves_the_bar_with_it(self):
        # The exact failure: boilerplate stripping lowered every score by a few
        # points and a fixed bar started withholding good postings.
        before = scores(*range(50, 100))
        after = [s - 5 for s in before]
        self.assertEqual(digest.percentile_bar(before, 0.90) - 5,
                         digest.percentile_bar(after, 0.90))

    def test_no_postings_yields_a_bar_of_zero_rather_than_raising(self):
        self.assertEqual(digest.percentile_bar([], 0.90), 0.0)

    def test_a_single_score_is_its_own_bar(self):
        self.assertEqual(digest.percentile_bar([72.0], 0.90), 72.0)

    def test_disqualified_postings_do_not_drag_the_bar_down(self):
        with_dq = digest.percentile_bar(scores(-1, -1, -1, 50, 60, 70, 80, 90), 0.90)
        without = digest.percentile_bar(scores(50, 60, 70, 80, 90), 0.90)
        self.assertEqual(with_dq, without)


class SelectionTests(unittest.TestCase):
    def rows(self, *totals):
        return [{"id": f"j{i}", "total": t} for i, t in enumerate(totals)]

    def test_only_postings_at_or_above_the_bar_are_selected(self):
        picked = digest.select(self.rows(90, 80, 40), bar=50, limit=10)
        self.assertEqual([r["total"] for r in picked], [90, 80])

    def test_the_limit_caps_a_flood(self):
        picked = digest.select(self.rows(*range(90, 60, -1)), bar=0, limit=5)
        self.assertEqual(len(picked), 5)

    def test_the_best_survive_the_cap_not_the_first_seen(self):
        picked = digest.select(self.rows(60, 95, 70), bar=0, limit=1)
        self.assertEqual(picked[0]["total"], 95)

    def test_nothing_above_the_bar_sends_nothing(self):
        self.assertEqual(digest.select(self.rows(10, 20), bar=50, limit=10), [])

    def test_a_barren_day_is_silence_not_a_padded_list(self):
        # A rank cap alone would send the best of a bad batch every morning.
        self.assertEqual(digest.select(self.rows(1, 2, 3), bar=50, limit=10), [])

    def test_the_held_back_count_is_reported_so_nothing_vanishes_quietly(self):
        picked, held = digest.select_with_overflow(self.rows(*range(90, 60, -1)), bar=0, limit=5)
        self.assertEqual(len(picked), 5)
        self.assertEqual(held, 25)


class AppliedDigestTests(unittest.TestCase):
    """The half of a job search that rots: drafted and never sent."""

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)

    def tearDown(self):
        self.con.close()

    def add(self, jid, status, days_ago=0, company="co"):
        self.con.execute(
            """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                 description, posted_at, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (jid, "s", company, "Engineer", "Remote", 1, "http://x", "d", None, "2026-01-01", "2026-01-01"))
        when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
        self.con.execute(
            "INSERT INTO applications (job_id, status, notes, updated_at) VALUES (?,?,?,?)",
            (jid, status, None, when))
        self.con.commit()

    def test_each_status_is_counted(self):
        self.add("a", "interested")
        self.add("b", "drafted")
        self.add("c", "drafted")
        counts = digest.applied_summary(self.con)["counts"]
        self.assertEqual(counts["drafted"], 2)
        self.assertEqual(counts["interested"], 1)

    def test_a_draft_sitting_too_long_is_surfaced(self):
        self.add("a", "drafted", days_ago=9)
        stale = digest.applied_summary(self.con, stale_days=5)["stale_drafts"]
        self.assertEqual([r["job_id"] for r in stale], ["a"])

    def test_a_fresh_draft_is_not_nagged_about(self):
        self.add("a", "drafted", days_ago=1)
        self.assertEqual(digest.applied_summary(self.con, stale_days=5)["stale_drafts"], [])

    def test_a_sent_application_with_no_movement_is_surfaced(self):
        self.add("a", "sent", days_ago=30)
        silent = digest.applied_summary(self.con, silent_days=14)["silent_sent"]
        self.assertEqual([r["job_id"] for r in silent], ["a"])

    def test_a_recently_sent_application_is_left_alone(self):
        self.add("a", "sent", days_ago=2)
        self.assertEqual(digest.applied_summary(self.con, silent_days=14)["silent_sent"], [])

    def test_a_closed_application_is_never_nagged_about(self):
        self.add("a", "rejected", days_ago=60)
        self.add("b", "closed", days_ago=60)
        s = digest.applied_summary(self.con)
        self.assertEqual(s["stale_drafts"], [])
        self.assertEqual(s["silent_sent"], [])

    def test_recent_rejections_are_reported(self):
        self.add("a", "rejected", days_ago=2)
        self.assertEqual(len(digest.applied_summary(self.con, recent_days=7)["recent_rejections"]), 1)

    def test_an_empty_pipeline_is_an_empty_summary_not_a_crash(self):
        s = digest.applied_summary(self.con)
        self.assertEqual(s["counts"], {})
        self.assertEqual(s["stale_drafts"], [])

    def test_the_summary_names_the_company_so_it_is_actionable(self):
        self.add("a", "drafted", days_ago=9, company="stripe")
        self.assertEqual(digest.applied_summary(self.con, stale_days=5)["stale_drafts"][0]["company"], "stripe")


class RenderTests(unittest.TestCase):
    def test_an_empty_section_prints_nothing_at_all(self):
        # Standing rule: a section with nothing to say says nothing, rather than
        # saying "nothing to report" in every email forever.
        self.assertEqual(digest.render_applied({"counts": {}, "stale_drafts": [],
                                                "silent_sent": [], "recent_rejections": []}), "")

    def test_counts_are_rendered_when_there_is_a_pipeline(self):
        out = digest.render_applied({"counts": {"drafted": 2}, "stale_drafts": [],
                                     "silent_sent": [], "recent_rejections": []})
        self.assertIn("drafted", out)

    def test_a_stale_draft_is_named_with_its_age(self):
        out = digest.render_applied({"counts": {"drafted": 1},
                                     "stale_drafts": [{"job_id": "a", "company": "stripe",
                                                       "title": "Engineer", "days": 9}],
                                     "silent_sent": [], "recent_rejections": []})
        self.assertIn("stripe", out)
        self.assertIn("9", out)


if __name__ == "__main__":
    unittest.main()
