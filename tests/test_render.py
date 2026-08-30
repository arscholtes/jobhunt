"""Rendering a whole variant, end to end.

Written after 165 tests passed green while skills() raised NameError on every
call. Nothing exercised the full path, so a broken renderer looked healthy. The
value of these is not the assertions — it is that they call the thing.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import resume  # noqa: E402

SHAPES = ["backend", "platform", "fullstack", "fde", "generic"]
DOMAINS = ["ai", "devtools", "rails", "general"]
EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "resume.example.toml"


def _facts():
    """The tracked example, so this runs in CI where the personal file is absent."""
    return resume.load(EXAMPLE)


class EveryVariantRenders(unittest.TestCase):
    def test_all_twenty_render_without_raising(self):
        facts = _facts()
        for shape in SHAPES:
            for domain in DOMAINS:
                with self.subTest(variant=f"{shape}.{domain}"):
                    text = resume.generate(shape, domain, facts)
                    self.assertTrue(text.strip(), "rendered empty")

    def test_the_document_carries_its_required_sections(self):
        text = resume.generate("backend", "rails", _facts())
        for heading in ("# ", "## Summary", "## Skills"):
            self.assertIn(heading, text)

    def test_contact_details_are_in_the_body(self):
        """ATS parsers ignore headers and footers, so contact has to be body text."""
        facts = _facts()
        text = resume.generate("generic", "general", facts)
        self.assertIn(facts["me"]["email"], text)

    def test_no_placeholder_reaches_a_reader(self):
        for shape in SHAPES:
            for domain in DOMAINS:
                with self.subTest(variant=f"{shape}.{domain}"):
                    self.assertNotIn("TODO", resume.generate(shape, domain, _facts()))

    def test_the_output_is_single_column_plain_text(self):
        """No tables and no markup: table content was dropped by 5 of 8 parsers.

        A pipe alone is not a table — it separates the contact line and a role's
        location. A markdown table needs a delimiter row, so that is what is
        checked; asserting on the bare character failed on correct output.
        """
        text = resume.generate("backend", "general", _facts())
        self.assertNotRegex(text, r"\n *\|? *:?-{3,}")
        self.assertNotIn("<", text)


class BulletsKeepTheirAuthoringOrder(unittest.TestCase):
    """Rank decides which bullets survive; the author decides the sequence.

    Sorting survivors by score made a role open with its trophy and mention being
    founded third — each bullet strong, the story incoherent.
    """

    def test_a_lower_weighted_bullet_written_first_still_prints_first(self):
        facts = _facts()
        facts["roles"] = [{
            "company": "Example", "title": "Engineer", "start": "2020", "end": "2021",
            "bullets": [
                {"text": "FIRST but weak", "shapes": [], "domains": [], "weight": 1},
                {"text": "SECOND but strong", "shapes": [], "domains": [], "weight": 10},
            ],
        }]
        text = resume.generate("generic", "general", facts)
        self.assertLess(text.index("FIRST but weak"), text.index("SECOND but strong"))


if __name__ == "__main__":
    unittest.main()
