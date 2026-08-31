"""Friction is a property of the ATS, not of the hostname.

24 of 69 shortlist postings reported unknown friction because the apply link is a
company-hosted careers page — www.brex.com, careers.datadoghq.com — sitting in
front of a Greenhouse form. The host is unrecognised; the ATS is not. The row
already records which board it was fetched from, and that is authoritative.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import signals


class FrictionFallsBackToTheSource(unittest.TestCase):
    def test_a_company_hosted_greenhouse_link_is_still_low_friction(self):
        job = {"title": "Engineer", "description": "",
               "url": "https://www.brex.com/careers/8617115002?gh_jid=8617115002",
               "source": "greenhouse"}
        self.assertEqual(signals.extract(job)["friction"], "low")

    def test_a_recognised_host_still_wins(self):
        job = {"title": "Engineer", "description": "",
               "url": "https://boards.greenhouse.io/x/jobs/1", "source": "greenhouse"}
        self.assertEqual(signals.extract(job)["friction"], "low")

    def test_unknown_stays_unknown_when_neither_is_known(self):
        job = {"title": "Engineer", "description": "",
               "url": "https://example.com/apply", "source": "somethingelse"}
        self.assertEqual(signals.extract(job)["friction"], "unknown")
