"""One board failing must not cost the boards after it.

fetch reads every [[boards]] entry in turn. A board that is down, renamed or
misspelt is reported and skipped. Ending the run there would leave every later
board unread until someone noticed the shortlist had gone quiet.
"""

import io
import sqlite3
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import cli, store
from jobhunt.sources import greenhouse
from jobhunt.sources._http import FetchError

DOWN = {"source": "greenhouse", "token": "tailspin"}
UP = {"source": "greenhouse", "token": "wingtip"}


def answer(url):
    """The Greenhouse API as get_json would see it: tailspin is down, wingtip answers."""
    if "/tailspin/" in url:
        raise FetchError(f"{url} returned HTTP 404")
    return {"jobs": [{"id": 1, "title": "Backend Engineer", "location": {"name": "Remote"},
                      "absolute_url": "https://job-boards.greenhouse.io/wingtip/jobs/1",
                      "content": "<p>Build services.</p>",
                      "updated_at": "2026-10-01T12:00:00-04:00"}]}


class FetchCommandTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript(store.SCHEMA)

    def tearDown(self):
        self.con.close()

    def run_cmd(self, *boards):
        buf = io.StringIO()
        with mock.patch.object(store, "connect", return_value=self.con), \
             mock.patch.object(cli, "_load_profile", return_value={"boards": list(boards)}), \
             mock.patch.object(greenhouse, "get_json", side_effect=answer), \
             redirect_stdout(buf):
            cli.cmd_fetch(SimpleNamespace(profile=None))
        return buf.getvalue()

    def stored(self):
        return [r[0] for r in self.con.execute("SELECT id FROM jobs")]

    def test_a_board_that_fails_does_not_stop_the_boards_after_it(self):
        self.run_cmd(DOWN, UP)
        self.assertEqual(self.stored(), ["greenhouse:wingtip:1"])

    def test_the_failed_board_is_reported_as_skipped_with_its_reason(self):
        out = self.run_cmd(DOWN, UP)
        line = next(x for x in out.splitlines() if "greenhouse/tailspin" in x)
        self.assertIn("skipped", line)
        self.assertIn("HTTP 404", line)

    def test_an_unknown_source_is_skipped_rather_than_ending_the_run(self):
        out = self.run_cmd({"source": "greenhous", "token": "tailspin"}, UP)
        self.assertEqual(self.stored(), ["greenhouse:wingtip:1"])
        self.assertIn("unknown source", out)

    def test_a_posting_fetched_before_is_counted_as_known_not_new(self):
        self.run_cmd(DOWN, UP)
        self.assertIn("0 new, 1 already known.", self.run_cmd(DOWN, UP))

    def test_a_profile_with_no_boards_stops_with_an_error(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cmd()
        self.assertIn("no [[boards]]", str(caught.exception.code))


if __name__ == "__main__":
    unittest.main()
