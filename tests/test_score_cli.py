"""Scoring the whole store: shared preambles, dealbreakers and the zero floor.

score.py's tests hand each rule a posting and the boilerplate to strip. In use,
cmd_score finds the boilerplate itself, across every posting a company has
stored, and then applies dealbreakers and [signals] on top. These tests run that
command over one company's three postings, because any of those steps can be
wired up wrong while every rule passes on its own.
"""

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import cli, export, store

PREAMBLE = ("At Fabrikam we build with Ruby, Rails, Postgres, Kubernetes, Go and "
            "Terraform across a distributed team. ") * 3

PROFILE = {
    "search": {"titles": ["backend engineer"], "exclude_titles": [], "locations": ["remote"],
               "remote_only": False},
    "skills": {"ruby": 5, "rails": 5, "postgres": 3, "kubernetes": 2, "go": 2, "terraform": 1},
    "interests": {},
    "dealbreakers": [{"pattern": "security clearance", "why": "not eligible"}],
    "signals": {"interview_live_coding": -100},
}


def posting(n, title, role_text):
    return {"id": f"greenhouse:fabrikam:{n}", "source": "greenhouse", "company": "Fabrikam",
            "title": title, "location": "Remote", "remote": 1,
            "url": f"https://job-boards.greenhouse.io/fabrikam/jobs/{n}",
            "description": PREAMBLE + role_text, "posted_at": None}


class ScoreCommandTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        # Each role text opens with a different letter so the shared prefix ends
        # exactly where the preamble does.
        store.upsert_jobs(self.con, [
            posting(1, "Field Engineer", "Travel to customer sites to install hardware."),
            posting(2, "Backend Engineer", "Requires an active security clearance."),
            posting(3, "Marketing Lead", "Expect a live coding interview."),
        ])
        self._tmp = tempfile.TemporaryDirectory()
        buf = io.StringIO()
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(export, "DEFAULT_PATH", Path(self._tmp.name) / "shortlist.csv"), \
             mock.patch.object(cli, "_load_profile", return_value=PROFILE), \
             redirect_stdout(buf):
            cli.cmd_score(SimpleNamespace(profile=None))
        self.out = buf.getvalue()

    def tearDown(self):
        self.con.close()
        self._tmp.cleanup()

    def scored(self, n):
        row = self.con.execute("SELECT total, breakdown FROM scores WHERE job_id = ?",
                               (f"greenhouse:fabrikam:{n}",)).fetchone()
        return row["total"], json.loads(row["breakdown"])

    def test_skills_named_only_in_the_company_preamble_earn_nothing(self):
        _, breakdown = self.scored(1)
        self.assertEqual((breakdown["skills"], breakdown["skills_matched"]), (0, []))

    def test_the_strip_is_reported_for_the_company(self):
        self.assertIn("boilerplate stripped for 1 company", self.out)

    def test_a_dealbreaker_is_saved_as_minus_one_with_its_reason(self):
        self.assertEqual(self.scored(2),
                         (-1, {"disqualified": "security clearance (not eligible)"}))

    def test_a_negative_signal_never_takes_a_score_below_zero(self):
        total, _ = self.scored(3)
        self.assertEqual(total, 0.0)

    def test_the_signal_that_moved_a_score_is_recorded(self):
        _, breakdown = self.scored(3)
        self.assertEqual(breakdown["signals"], ["-100 interview:live_coding"])


if __name__ == "__main__":
    unittest.main()
