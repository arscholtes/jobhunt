"""region_locked must fire on roles Alex cannot take, and not on ones he can.

A flag that fires on the wrong row trains him to ignore every flag, so the
precision matters as much as the recall. The real case: a vanta posting whose
location is 'Remote U.S.' was flagged region_locked '[canada]' because the
string appeared in the benefits boilerplate ('Offices in SF, NYC, London,
Dublin, Tel Aviv, and Sydney [Canada] What you can expect...').

The bracketed-country pattern is a TITLE tag convention. Run against the body
it matches any bracketed country word in prose.
"""

import inspect
import unittest

from jobhunt import cli, gate

PERKS = ("Offices in SF, NYC, London, Dublin, Tel Aviv, and Sydney [Canada] "
         "What you can expect as an employee: competitive salary and equity.")


def flags(title="Senior Software Engineer", description="", location="Remote U.S."):
    return dict(gate.decide(
        {"title": title, "description": description, "location": location}).get("flags") or [])


class RegionLockPrecision(unittest.TestCase):
    def test_bracketed_country_in_body_prose_does_not_fire(self):
        self.assertNotIn("region_locked", flags(description=PERKS))

    def test_bracketed_country_in_title_still_fires(self):
        self.assertIn("region_locked", flags(title="Senior Software Engineer [Canada]"))

    def test_country_only_phrasing_in_body_still_fires(self):
        self.assertIn("region_locked", flags(description="This role is Canada-only."))

    def test_must_reside_phrasing_in_body_still_fires(self):
        self.assertIn("region_locked", flags(description="You must be located in Canada."))

    def test_eligibility_phrasing_in_body_still_fires(self):
        self.assertIn("region_locked", flags(description="Must be eligible to work in the UK."))

    def test_us_remote_posting_carries_no_region_flag(self):
        self.assertEqual({}, flags(description="A normal posting about Ruby and Rails."))


class LocationReachesTheGate(unittest.TestCase):
    """cmd_gate and cmd_resume built a dict of title+description only, so no
    location-derived flag could ever appear on either path — while cmd_gate
    prints the location one line above the flags it omitted."""

    def test_international_flag_needs_the_location_key(self):
        with_loc = flags(location="Argentina Remote")
        self.assertIn("international", with_loc)
        without = dict(gate.decide(
            {"title": "Senior Software Engineer", "description": ""}).get("flags") or [])
        self.assertNotIn("international", without)

    def test_cli_gate_passes_location_through(self):
        for fn in (cli.cmd_gate, cli.cmd_resume):
            src = inspect.getsource(fn)
            self.assertNotIn('{"title": r["title"], "description": r["description"]}', src,
                             f"{fn.__name__} still drops location before gate.decide")


if __name__ == "__main__":
    unittest.main()
