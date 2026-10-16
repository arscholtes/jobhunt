"""The shortlist as a spreadsheet.

Written to iCloud Drive so it is on the phone without a second mechanism, and
regenerated rather than appended so it can never disagree with the database.
"""
import csv
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import export

ROWS = [
    {"id": "greenhouse:acme:1", "company": "acme", "title": "Senior Engineer",
     "location": "Remote", "remote": 1, "url": "https://x/1", "total": 88.5,
     "first_seen": "2026-08-30T10:00:00+00:00", "status": "interested"},
    {"id": "lever:beta:2", "company": "beta", "title": "Backend Engineer",
     "location": "Dublin, Ireland", "remote": 0, "url": "https://x/2", "total": 61.0,
     "first_seen": "2026-08-29T10:00:00+00:00", "status": ""},
]


class Export(unittest.TestCase):
    def test_it_writes_a_readable_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            path = export.write(ROWS, pathlib.Path(d) / "shortlist.csv")
            with path.open() as fh:
                rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["company"], "acme")

    def test_the_best_match_is_first(self):
        with tempfile.TemporaryDirectory() as d:
            path = export.write(ROWS, pathlib.Path(d) / "s.csv")
            rows = list(csv.DictReader(path.open()))
        self.assertEqual(rows[0]["score"], "88.5")

    def test_it_replaces_rather_than_appends(self):
        """Regenerated, never grown — an appended sheet drifts from the database."""
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "s.csv"
            export.write(ROWS, p)
            export.write(ROWS[:1], p)
            self.assertEqual(len(list(csv.DictReader(p.open()))), 1)

    def test_the_apply_url_survives(self):
        with tempfile.TemporaryDirectory() as d:
            rows = list(csv.DictReader(export.write(ROWS, pathlib.Path(d) / "s.csv").open()))
        self.assertEqual(rows[0]["apply"], "https://x/1")
