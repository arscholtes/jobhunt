"""gate.decide must accept what the CLI actually hands it: a sqlite3.Row.

Every existing gate test builds a plain dict, so classify()'s job.get() calls
were never exercised against a Row. `jobhunt gate` and `jobhunt resume` both
pass one straight from the jobs table, and both raised AttributeError for every
posting in the store while the suite stayed green.
"""
import pathlib
import sqlite3
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import cli


class GateAcceptsARowFromTheJobsTable(unittest.TestCase):
    def _con(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("""CREATE TABLE jobs (
            id TEXT PRIMARY KEY, source TEXT, company TEXT, title TEXT,
            location TEXT, remote INTEGER, url TEXT, description TEXT,
            posted_at TEXT, first_seen TEXT, last_seen TEXT)""")
        con.execute(
            "INSERT INTO jobs (id, source, company, title, location, remote, url, description)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("workday:acme:R-1", "workday", "Acme", "Sr. Software Engineer (AI First)",
             "Remote, United States", 1, "https://example.invalid/job",
             "Backend development in Ruby. APIs and distributed systems. React and TypeScript a plus."))
        con.commit()
        return con

    def test_the_row_the_cli_fetches_is_a_mapping_gate_can_read(self):
        from jobhunt import gate
        row = cli._job(self._con(), "workday:acme:R-1")
        decision = gate.decide(row)                      # raised AttributeError
        self.assertIn("variant", decision)
        self.assertTrue(decision["variant"])

    def test_the_row_still_supports_the_field_access_the_commands_use(self):
        row = cli._job(self._con(), "workday:acme:R-1")
        self.assertEqual(row["company"], "Acme")
        self.assertEqual(row["location"], "Remote, United States")


if __name__ == "__main__":
    unittest.main()
