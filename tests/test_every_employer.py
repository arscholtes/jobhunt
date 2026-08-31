"""A resume may reorder or trim bullets within a job. It must never remove a job.

bullets_for() spent a fixed bullet budget top-down by relevance, so a
high-ranking employer could take all of it and a lower-ranked one got no room —
and a role with no room was dropped entirely, heading and dates with it.

Measured across twelve generated packets: three omitted Demandwell and replit
omitted both Demandwell and Peerview, leaving a resume showing one five-month
job. That is not a formatting problem. Omitting an employer misstates work
history on an application form and manufactures an employment gap that did not
happen.

Page budget was never the constraint: the packets carrying all three employers
render at exactly the same two pages as the ones missing one.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import resume, tailor

FACTS = {
    "me": {"name": "A"}, "summaries": {"default": "s"}, "skill_groups": [],
    "projects": [], "education": {"lines": []},
    "roles": [
        {"company": "Big", "title": "Eng", "start": "2024-01", "end": "present",
         "bullets": [{"text": f"Rails Postgres thing {i}", "weight": 9} for i in range(10)]},
        {"company": "Middle", "title": "Eng", "start": "2021-10", "end": "2023-01",
         "role_priority": 2,
         "bullets": [{"text": "Did something unrelated", "weight": 7}]},
        {"company": "Small", "title": "Eng", "start": "2023-02", "end": "2023-10",
         "role_priority": 1,
         "bullets": [{"text": "Also unrelated", "weight": 6}]},
    ],
}
JOB = {"id": "x", "title": "Senior Rails Engineer", "company": "c", "url": "u",
       "location": "Remote", "remote": 1,
       "description": "We need Rails and Postgres experience."}


class EveryEmployerTests(unittest.TestCase):
    def companies(self, placed):
        return [c for c, _, _ in placed]

    def test_no_employer_is_dropped_when_one_role_could_take_the_budget(self):
        placed = tailor.bullets_for(FACTS["roles"], JOB, budget=8)
        self.assertEqual(set(self.companies(placed)), {"Big", "Middle", "Small"})

    def test_every_employer_survives_a_budget_smaller_than_the_role_count(self):
        placed = tailor.bullets_for(FACTS["roles"], JOB, budget=1)
        self.assertEqual(len(placed), 3)

    def test_a_role_with_no_relevant_bullets_still_appears(self):
        placed = tailor.bullets_for(FACTS["roles"], JOB, budget=8)
        self.assertIn("Small", self.companies(placed))

    def test_roles_stay_in_resume_order(self):
        placed = tailor.bullets_for(FACTS["roles"], JOB, budget=8)
        self.assertEqual(self.companies(placed), ["Big", "Middle", "Small"])

    def test_a_role_may_render_with_no_bullets_at_all(self):
        # Presence is the requirement; bullets there are optional.
        placed = tailor.bullets_for(FACTS["roles"], JOB, budget=1)
        self.assertTrue(any(len(b) == 0 for _, _, b in placed))


class ScarcityPreferenceTests(unittest.TestCase):
    """When bullets are scarce, the preference is data, not a hardcoded name."""

    def test_the_higher_priority_role_keeps_its_bullet_first(self):
        placed = tailor.bullets_for(FACTS["roles"], JOB, budget=2)
        by_company = {c: b for c, _, b in placed}
        self.assertTrue(by_company["Middle"], "the preferred role lost its bullet first")

    def test_no_company_name_appears_in_the_module(self):
        src = (Path(__file__).resolve().parent.parent / "jobhunt" / "tailor.py").read_text()
        for name in ("Demandwell", "Peerview", "Liftify"):
            self.assertNotIn(name, src, f"{name} is hardcoded in tailor.py")

    def test_a_role_without_a_priority_still_places(self):
        roles = [dict(r) for r in FACTS["roles"]]
        roles[1].pop("role_priority", None)
        placed = tailor.bullets_for(roles, JOB, budget=3)
        self.assertEqual(len(placed), 3)


class VariantTests(unittest.TestCase):
    """resume.build() drops a role the same way, on a different code path."""

    def test_every_employer_appears_in_a_built_variant(self):
        doc = resume.build(FACTS, "backend", "rails")
        self.assertEqual({r["company"] for r in doc["roles"]}, {"Big", "Middle", "Small"})

    def test_a_role_whose_bullets_are_all_ineligible_still_appears(self):
        facts = {**FACTS, "roles": [
            {**FACTS["roles"][0]},
            {"company": "Tagged Out", "title": "Eng", "start": "2020-01", "end": "2021-01",
             "bullets": [{"text": "x", "weight": 5, "shapes": ["fde"]}]},
        ]}
        doc = resume.build(facts, "backend", "rails")
        self.assertIn("Tagged Out", {r["company"] for r in doc["roles"]})

    def test_every_real_variant_carries_every_real_employer(self):
        real = resume.load()
        expected = {r["company"] for r in real["roles"]}
        for shape in ("backend", "fullstack", "platform", "fde", "generic"):
            for domain in ("ai", "devtools", "rails", "general"):
                doc = resume.build(real, shape, domain)
                self.assertEqual({r["company"] for r in doc["roles"]}, expected,
                                 f"{shape}.{domain} dropped an employer")


if __name__ == "__main__":
    unittest.main()


class PageBudgetTests(unittest.TestCase):
    """Restoring every employer cost nothing on length, and must keep costing nothing."""

    def test_no_rendered_packet_runs_past_two_pages(self):
        out = Path(__file__).resolve().parent.parent / "out" / "apply"
        pdfs = list(out.glob("*.pdf")) if out.exists() else []
        if not pdfs:
            self.skipTest("no rendered packets")
        for pdf in pdfs:
            pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
            self.assertLessEqual(pages, 2, f"{pdf.stem} runs to {pages} pages")

    def test_every_rendered_packet_names_every_employer(self):
        out = Path(__file__).resolve().parent.parent / "out" / "apply"
        mds = list(out.glob("*.md")) if out.exists() else []
        if not mds:
            self.skipTest("no packets")
        companies = [r["company"] for r in resume.load()["roles"]]
        for md in mds:
            text = md.read_text()
            for company in companies:
                self.assertIn(company, text, f"{md.stem} omits {company}")


class DemandwellBulletsTests(unittest.TestCase):
    """Presence was the floor. Demandwell is meant to carry real bullets.

    A second cause, separate from the budget: both Demandwell bullets were tagged
    backend/fde/generic only, so _eligible() filtered every one of them out on a
    fullstack- or platform-shaped variant and the role yielded nothing. Peerview
    carried fullstack tags and always survived, which is why Demandwell was
    missing from exactly the four full-stack postings.

    Fixing the budget alone left Demandwell exposed to the tag filter; fixing the
    tags alone would leave other roles exposed to the budget.
    """

    def test_demandwell_carries_at_least_one_bullet_in_every_variant(self):
        facts = resume.load()
        for shape in ("backend", "fullstack", "platform", "fde", "generic"):
            for domain in ("ai", "devtools", "rails", "general"):
                doc = resume.build(facts, shape, domain)
                role = next(r for r in doc["roles"] if r["company"] == "Demandwell")
                self.assertTrue(role["bullets"],
                                f"{shape}.{domain} leaves Demandwell with no bullets")

    def test_the_role_order_is_data_not_code(self):
        facts = resume.load()
        by_company = {r["company"]: r.get("role_priority") for r in facts["roles"]}
        self.assertGreater(by_company["Liftify"], by_company["Demandwell"])
        self.assertGreater(by_company["Demandwell"], by_company["Peerview Data"])

    def test_scarce_bullets_reach_demandwell_before_peerview(self):
        facts = resume.load()
        job = {"id": "x", "title": "Senior Full Stack Engineer", "company": "c",
               "url": "u", "location": "Remote", "remote": 1,
               "description": "Rails and React."}
        placed = tailor.bullets_for(facts["roles"], job, shape="fullstack",
                                    domain="general", budget=8)
        counts = {c: len(b) for c, _, b in placed}
        self.assertGreaterEqual(counts.get("Demandwell", 0), 1)

    def test_peerview_presence_alone_is_acceptable(self):
        # "just note I was at peerview" — a heading with no bullets is a pass.
        facts = resume.load()
        job = {"id": "x", "title": "Senior Full Stack Engineer", "company": "c",
               "url": "u", "location": "Remote", "remote": 1, "description": "Rails."}
        placed = tailor.bullets_for(facts["roles"], job, shape="fullstack",
                                    domain="general", budget=8)
        self.assertIn("Peerview Data", [c for c, _, _ in placed])
