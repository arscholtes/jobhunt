"""The sheet regenerates with the daily run, and the digest says where it is.

Two failure modes worth pinning down. The sheet must carry the WHOLE shortlist,
not the day's unsent delta — it is for browsing, and a spreadsheet that only ever
holds what was new this morning is not that. And the link must work on the device
he reads it on: a file:// URL is live in desktop Mail and inert in iOS Mail, so
shipping only that is shipping something that silently does nothing on a phone.
"""

import io
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


class ExportContentTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        # Twenty rows so the 90th percentile leaves two above it. With ten or
        # fewer the p90 index IS the top row, and every "above the bar" assertion
        # collapses to a single posting.
        for i, total in enumerate([95, 88] + [40 - n for n in range(18)]):
            jid = f"j{i}"
            self.con.execute(
                """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                     description, posted_at, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (jid, "s", "co", f"Engineer {i}", "Remote", 1, "http://x", "d", None,
                 "2026-01-01", "2026-01-01"))
            self.con.execute(
                "INSERT INTO scores (job_id, total, breakdown, scored_at) VALUES (?,?,?,?)",
                (jid, total, "{}", "2026-01-01"))
        self.con.commit()
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "shortlist.csv"

    def tearDown(self):
        self.con.close()
        self._tmp.cleanup()

    def run_digest(self):
        args = SimpleNamespace(dry_run=True, limit=20, profile=None, resume=None)
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(export, "DEFAULT_PATH", self.path), \
             redirect_stdout(io.StringIO()) as buf:
            cli.cmd_digest(args)
        return buf.getvalue()

    def test_the_sheet_is_written_by_the_daily_run(self):
        self.run_digest()
        self.assertTrue(self.path.exists())

    def test_the_sheet_carries_the_whole_shortlist_not_the_unsent_delta(self):
        # Everything at or above the bar, including what was emailed days ago.
        store.mark_notified(self.con, ["j0"])
        self.run_digest()
        body = self.path.read_text()
        self.assertIn("Engineer 0", body, "an already-sent posting fell out of the sheet")
        self.assertIn("Engineer 1", body)

    def test_postings_below_the_bar_stay_out_of_the_sheet(self):
        self.run_digest()
        self.assertNotIn("Engineer 9", self.path.read_text())

    def test_the_sheet_is_regenerated_rather_than_appended(self):
        self.run_digest()
        first = self.path.read_text()
        self.run_digest()
        self.assertEqual(first, self.path.read_text())

    def test_the_digest_says_where_the_sheet_went(self):
        self.assertIn("shortlist.csv", self.run_digest())

    def test_a_failed_export_does_not_take_the_digest_down(self):
        args = SimpleNamespace(dry_run=True, limit=20, profile=None, resume=None)
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(export, "write", side_effect=OSError("no icloud")), \
             redirect_stdout(io.StringIO()) as buf:
            cli.cmd_digest(args)
        self.assertIn("would send", buf.getvalue().lower())


class LinkTests(unittest.TestCase):
    """One URL does not work in both places, so both are given."""

    def test_the_desktop_link_is_a_file_url(self):
        lines = cli.sheet_reference(Path("/Users/x/iCloud/jobhunt/shortlist.csv"))
        self.assertTrue(any(line.startswith("file://") or "file://" in line for line in lines))

    def test_the_phone_case_is_answered_in_words_not_a_link(self):
        lines = cli.sheet_reference(Path("/Users/x/iCloud/jobhunt/shortlist.csv"))
        joined = " ".join(lines).lower()
        self.assertIn("icloud", joined)
        self.assertIn("shortlist.csv", joined)

    def test_the_words_do_not_pretend_to_be_a_second_link(self):
        # A file:// URL is inert in iOS Mail; naming the folder is the honest form.
        lines = cli.sheet_reference(Path("/Users/x/iCloud/jobhunt/shortlist.csv"))
        phone = [line for line in lines if "file://" not in line]
        self.assertTrue(phone)
        self.assertFalse(any("http" in line for line in phone))


if __name__ == "__main__":
    unittest.main()


class MirrorTests(unittest.TestCase):
    """The sheet mirrors the database, rather than snapshotting it once a day.

    Called from cmd_score rather than only from cmd_digest, because scoring is
    where the data actually changes. Hooking the daily digest alone left the sheet
    up to 24 hours behind while the database moved under it — and a stale artifact
    that looks authoritative is the failure mode that has already appeared three
    times this week.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "shortlist.csv"
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        self.con.execute(
            """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                 description, posted_at, first_seen, last_seen)
               VALUES ('j','s','co','Engineer','Remote',1,'http://x','Rails',NULL,
                       '2026-01-01','2026-01-01')""")
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self._tmp.cleanup()

    def test_scoring_regenerates_the_sheet(self):
        args = SimpleNamespace(profile=None)
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(export, "DEFAULT_PATH", self.path), \
             mock.patch.object(cli, "_load_profile", return_value={
                 "search": {"titles": ["engineer"], "exclude_titles": [], "locations": [],
                            "remote_only": False},
                 "skills": {}, "interests": {}, "dealbreakers": []}), \
             redirect_stdout(io.StringIO()):
            cli.cmd_score(args)
        self.assertTrue(self.path.exists(), "scoring did not refresh the sheet")

    def test_a_failed_write_does_not_take_scoring_down(self):
        args = SimpleNamespace(profile=None)
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(export, "write", side_effect=OSError("no icloud")), \
             mock.patch.object(cli, "_load_profile", return_value={
                 "search": {"titles": [], "exclude_titles": [], "locations": [],
                            "remote_only": False},
                 "skills": {}, "interests": {}, "dealbreakers": []}), \
             redirect_stdout(io.StringIO()) as buf:
            cli.cmd_score(args)
        self.assertIn("scored", buf.getvalue())
