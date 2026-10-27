"""The commands that read one posting, reached the way a person types them.

Each is a little SQL and printing behind argparse, so what breaks is the wiring:
a subcommand bound to the wrong function, an option that never reaches the
store, or a sqlite Row handed to code that calls .get() on it. These go through
cli.main with a real argument list and an in-memory store.
"""

import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import cli, resume, store
from tests.resumes import CANDIDATE

JID = "greenhouse:fabrikam:7"


class DisplayCommandTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)
        store.upsert_jobs(self.con, [{
            "id": JID, "source": "greenhouse", "company": "Fabrikam",
            "title": "Senior Backend Engineer", "location": "Remote", "remote": 1,
            "url": "https://job-boards.greenhouse.io/fabrikam/jobs/7",
            "description": "<h3>Requirements</h3><ul><li>Experience with Ruby on Rails</li></ul>",
            "posted_at": None}])
        store.save_score(self.con, JID, 72.5, {"title": 30})

    def tearDown(self):
        self.con.close()

    def run_cli(self, *argv):
        buf = io.StringIO()
        # resume.PATH points at the fictional candidate, so brief and resume
        # never read a resume.toml from the checkout.
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(resume, "PATH", CANDIDATE), \
             redirect_stdout(buf):
            cli.main(list(argv))
        return buf.getvalue()

    def test_show_prints_the_posting_and_its_score(self):
        out = self.run_cli("show", JID)
        self.assertIn("Senior Backend Engineer\nFabrikam", out)
        self.assertIn("score 72.5", out)

    def test_show_refuses_an_unknown_id(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("show", "greenhouse:fabrikam:404")
        self.assertIn("no job with id", str(caught.exception.code))

    def test_status_records_the_status_and_its_note(self):
        self.run_cli("status", JID, "interested", "--note", "referred by a former colleague")
        row = self.con.execute("SELECT status, notes FROM applications WHERE job_id = ?",
                               (JID,)).fetchone()
        self.assertEqual(tuple(row), ("interested", "referred by a former colleague"))

    def test_status_refuses_a_status_outside_the_list(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            self.run_cli("status", JID, "ghosted")
        self.assertEqual(caught.exception.code, 2)

    def test_gate_names_the_variant(self):
        self.assertIn("variant  ", self.run_cli("gate", JID))

    def test_resume_renders_the_variant_for_the_posting(self):
        self.assertIn("Test Candidate", self.run_cli("resume", JID))

    def test_resume_writes_to_the_file_it_is_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "resume.md"
            self.run_cli("resume", JID, "-o", str(out))
            self.assertIn("Test Candidate", out.read_text())

    def test_brief_gives_the_apply_link_and_its_friction(self):
        self.assertIn("https://job-boards.greenhouse.io/fabrikam/jobs/7  (low friction)",
                      self.run_cli("brief", JID))


if __name__ == "__main__":
    unittest.main()
