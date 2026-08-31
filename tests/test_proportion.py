"""Engineering work must outweigh the founder roles on an engineering resume.

Measured on fullstack.ai: 11 founder bullets against 7 engineering ones, with
Liftify — the current job and the most relevant thing on the page — showing three.

The cause is the tagging discipline itself, pointing the other way. Every founder
bullet is tagged for any shape and any domain, so none is ever filtered; Liftify's
ten are narrowly tagged, so most are filtered on any given variant. The same class
of defect as Demandwell being tagged out of full-stack, in reverse.

Two levers, both data: a per-role cap in resume.toml, and wider tags on the
bullets that are genuinely cross-shape. No bullet text changes — those are his
statements about his own work, and the founder material covers a real gap and is
deliberate.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import resume

SHAPES = ("backend", "fullstack", "platform", "fde", "generic")
DOMAINS = ("ai", "devtools", "rails", "general")


def split(facts, doc):
    kinds = {r["company"]: r.get("kind") for r in facts["roles"]}
    eng = sum(len(r["bullets"]) for r in doc["roles"] if kinds[r["company"]] == "employment")
    founder = sum(len(r["bullets"]) for r in doc["roles"] if kinds[r["company"]] == "founder")
    return eng, founder


class ProportionTests(unittest.TestCase):
    def test_engineering_outweighs_founder_in_every_variant(self):
        facts = resume.load()
        for shape in SHAPES:
            for domain in DOMAINS:
                eng, founder = split(facts, resume.build(facts, shape, domain))
                self.assertGreater(eng, founder,
                                   f"{shape}.{domain}: {eng} engineering vs {founder} founder")

    def test_the_current_role_carries_real_weight_everywhere(self):
        facts = resume.load()
        for shape in SHAPES:
            for domain in DOMAINS:
                doc = resume.build(facts, shape, domain)
                liftify = next(r for r in doc["roles"] if r["company"] == "Liftify")
                self.assertGreaterEqual(len(liftify["bullets"]), 4,
                                        f"{shape}.{domain} leaves Liftify with "
                                        f"{len(liftify['bullets'])}")

    def test_a_cap_is_a_cap_not_a_cut(self):
        # A capped role keeps its strongest material; it does not disappear.
        facts = resume.load()
        for shape in SHAPES:
            doc = resume.build(facts, shape, "general")
            for role in doc["roles"]:
                if (r := next(x for x in facts["roles"] if x["company"] == role["company"])).get("max_bullets"):
                    self.assertLessEqual(len(role["bullets"]), r["max_bullets"])
                    self.assertTrue(role["bullets"] or not r["bullets"])

    def test_every_employer_is_still_present(self):
        facts = resume.load()
        expected = {r["company"] for r in facts["roles"]}
        for shape in SHAPES:
            for domain in DOMAINS:
                got = {r["company"] for r in resume.build(facts, shape, domain)["roles"]}
                self.assertEqual(got, expected, f"{shape}.{domain} dropped an employer")

    def test_the_cap_lives_in_the_data_not_the_code(self):
        src = (Path(__file__).resolve().parent.parent / "jobhunt" / "resume.py").read_text()
        for name in ("Timeless", "Hour Zero", "Agile Esports", "Liftify"):
            self.assertNotIn(name, src, f"{name} is hardcoded in resume.py")


class NoRewordingTests(unittest.TestCase):
    """Tags may move. Claims may not."""

    EXPECTED_TEXT_COUNT = None

    def test_every_bullet_still_has_its_text(self):
        for role in resume.load()["roles"]:
            for b in role["bullets"]:
                self.assertTrue(b.get("text", "").strip())

    def test_no_bullet_text_was_truncated_into_an_ellipsis(self):
        for role in resume.load()["roles"]:
            for b in role["bullets"]:
                self.assertNotIn("…", b["text"])
                self.assertFalse(b["text"].rstrip().endswith("..."))


class PageTests(unittest.TestCase):
    def test_every_rendered_packet_is_still_two_pages(self):
        out = Path(__file__).resolve().parent.parent / "out" / "apply"
        pdfs = list(out.glob("*.pdf")) if out.exists() else []
        if not pdfs:
            self.skipTest("no rendered packets")
        for pdf in pdfs:
            pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
            self.assertLessEqual(pages, 2, f"{pdf.stem} runs to {pages} pages")


if __name__ == "__main__":
    unittest.main()
