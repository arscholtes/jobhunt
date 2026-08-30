"""The digest command a scheduled job can call.

digest.py existed as a module with nothing invoking it, so there was nothing for
launchd to run. The command is the deliverable; the dry run is what makes it
safe to arm.
"""

import io
import sqlite3
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import cli, store  # noqa: E402


class DigestCommandTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        for i, total in enumerate([95, 88, 40]):
            jid = f"j{i}"
            self.con.execute(
                """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                     description, posted_at, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (jid, "s", "co", f"Engineer {i}", "Remote", 1, "http://x",
                 "<h3>Requirements</h3><ul><li>Rails</li></ul>", None,
                 "2026-01-01", "2026-01-01"))
            self.con.execute(
                "INSERT INTO scores (job_id, total, breakdown, scored_at) VALUES (?,?,?,?)",
                (jid, total, "{}", "2026-01-01"))
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def run_cmd(self, **kw):
        args = SimpleNamespace(dry_run=True, limit=20, profile=None, resume=None)
        for k, v in kw.items():
            setattr(args, k, v)
        buf = io.StringIO()
        with mock.patch.object(store, "connect", return_value=self.con), \
             redirect_stdout(buf):
            cli.cmd_digest(args)
        return buf.getvalue()

    def test_a_dry_run_reports_what_it_would_send(self):
        self.assertIn("would send", self.run_cmd().lower())

    def test_a_dry_run_sends_nothing(self):
        with mock.patch("jobhunt.notify.send") as send:
            self.run_cmd()
        send.assert_not_called()

    def test_a_dry_run_marks_nothing_notified(self):
        self.run_cmd()
        self.assertEqual(
            self.con.execute("SELECT count(*) FROM notified").fetchone()[0], 0)

    def test_the_bar_is_reported_so_it_can_be_sanity_checked(self):
        self.assertIn("bar", self.run_cmd().lower())

    def test_postings_below_the_bar_are_not_included(self):
        out = self.run_cmd()
        self.assertNotIn("Engineer 2", out)

    def test_the_limit_caps_what_would_be_sent(self):
        out = self.run_cmd(limit=1)
        self.assertIn("1 posting", out)

    def test_an_already_notified_posting_is_not_resent(self):
        store.mark_notified(self.con, ["j0"])
        self.assertNotIn("Engineer 0", self.run_cmd())

    def test_nothing_to_send_is_said_plainly_rather_than_failing(self):
        store.mark_notified(self.con, ["j0", "j1", "j2"])
        self.assertIn("nothing", self.run_cmd().lower())


class SendOrderingTests(unittest.TestCase):
    """Marking before the send would lose a day's postings on a refused connection."""

    def test_nothing_is_marked_when_the_send_raises(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.executescript(store.SCHEMA)
        con.execute(
            """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                 description, posted_at, first_seen, last_seen)
               VALUES ('j','s','co','E','Remote',1,'http://x','d',NULL,'2026-01-01','2026-01-01')""")
        con.execute("INSERT INTO scores VALUES ('j', 90, '{}', '2026-01-01')")
        con.commit()

        args = SimpleNamespace(dry_run=False, limit=20, profile=None, resume=None)
        with mock.patch.object(store, "connect", return_value=con), \
             mock.patch("jobhunt.notify.send", side_effect=OSError("refused")), \
             redirect_stdout(io.StringIO()):
            try:
                cli.cmd_digest(args)
            except SystemExit:
                pass
        self.assertEqual(con.execute("SELECT count(*) FROM notified").fetchone()[0], 0)
        con.close()


if __name__ == "__main__":
    unittest.main()
