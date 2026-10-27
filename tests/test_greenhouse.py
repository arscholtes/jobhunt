"""The Greenhouse board, read the way its API actually answers.

Greenhouse can send a location whose name is null rather than absent: podium81
posting 8063639 did on 2026-10-16. A default passed to .get() covers only an
absent key, so that posting crashed the adapter, and the crash ended the whole
fetch run with every board after it left unread.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import greenhouse


def job(**changes):
    """One posting in the live API's shape, trimmed to the fields the adapter reads."""
    return {"id": 8063639, "title": "Customer Success Manager",
            "location": {"name": "Lehi, UT"},
            "absolute_url": "https://job-boards.greenhouse.io/podium81/jobs/8063639",
            "content": "<p>Help customers.</p>", "updated_at": "2026-10-01T12:00:00-04:00",
            **changes}


def fetch(*jobs):
    with mock.patch.object(greenhouse, "get_json", return_value={"jobs": list(jobs)}):
        return greenhouse.fetch("podium81")


class LocationTests(unittest.TestCase):
    def test_a_null_location_name_is_read_as_no_location(self):
        rows = fetch(job(location={"name": None}))
        self.assertEqual((rows[0]["location"], rows[0]["remote"]), ("", 0))


if __name__ == "__main__":
    unittest.main()
