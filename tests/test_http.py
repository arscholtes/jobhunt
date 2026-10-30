"""Every way a board can fail to answer becomes one error the fetch command expects.

cmd_fetch skips a board on FetchError and carries on with the rest. Any other
exception escaping get_json ends the whole run, leaving every board after the
failing one unread, so each failure urllib can raise has to arrive as FetchError.
"""

import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt.sources import _http

URL = "https://boards.example.com/v1/fabrikam/jobs"


def answering(body):
    """A urlopen stand-in that returns `body` as the response."""
    return mock.patch.object(_http.urllib.request, "urlopen", return_value=io.BytesIO(body))


def failing(error):
    return mock.patch.object(_http.urllib.request, "urlopen", side_effect=error)


class GetJsonTests(unittest.TestCase):
    def test_a_json_body_is_returned_parsed(self):
        with answering(b'{"jobs": [{"id": 1}]}'):
            self.assertEqual(_http.get_json(URL), {"jobs": [{"id": 1}]})

    def test_an_http_error_is_a_fetch_error_naming_the_status(self):
        error = urllib.error.HTTPError(URL, 503, "Service Unavailable", None, None)
        with failing(error), self.assertRaises(_http.FetchError) as caught:
            _http.get_json(URL)
        self.assertIn("HTTP 503", str(caught.exception))

    def test_an_unreachable_host_is_a_fetch_error_naming_the_reason(self):
        with failing(urllib.error.URLError("Name or service not known")), \
             self.assertRaises(_http.FetchError) as caught:
            _http.get_json(URL)
        self.assertIn("Name or service not known", str(caught.exception))

    def test_a_body_that_is_not_json_is_a_fetch_error(self):
        # A board that moved can answer 200 with an HTML page.
        with answering(b"<html>Moved</html>"), self.assertRaises(_http.FetchError):
            _http.get_json(URL)


if __name__ == "__main__":
    unittest.main()
