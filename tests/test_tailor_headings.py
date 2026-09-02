"""Requirement headings are not always heading tags.

Measured on 744 live postings: they mark a requirements section as
`<p><strong>Requirements</strong></p>` and only 249 use a real <h> tag. Matching
only <h1>-<h6> left the gap analysis — the one section that decides whether to
apply — silently blank on three quarters of the shortlist. Silently is the
problem: it printed "this posting states no requirements list" and was believed.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import tailor

BOLD_PARAGRAPH = (
    "<p>About the role</p> <ul> <li>Own the release pipeline</li> </ul> "
    "<p><strong>Requirements</strong></p> <ul> "
    "<li>7+ years of professional experience operating backend systems</li> "
    "<li>Strong proficiency in a backend language</li> </ul> "
    "<p><strong>Benefits</strong></p> <ul> <li>Dental and vision</li> </ul>"
)
HEADING_TAG = (
    "<h3>Requirements</h3> <ul> "
    "<li>7+ years of professional experience operating backend systems</li> </ul>"
)


class BoldParagraphHeadings(unittest.TestCase):
    def test_a_bold_paragraph_heading_is_a_heading(self):
        reqs = tailor.requirements({"description": BOLD_PARAGRAPH})
        self.assertTrue(reqs, "bold-paragraph requirements section was not found")
        self.assertTrue(any("7+ years" in r for r in reqs), reqs)

    def test_a_real_heading_tag_still_works(self):
        reqs = tailor.requirements({"description": HEADING_TAG})
        self.assertTrue(any("7+ years" in r for r in reqs), reqs)

    def test_the_section_ends_at_the_next_heading(self):
        """Benefits are not requirements. Reporting them as gaps kills trust."""
        reqs = tailor.requirements({"description": BOLD_PARAGRAPH})
        self.assertFalse(any("ental" in r for r in reqs), reqs)


if __name__ == "__main__":
    unittest.main()
