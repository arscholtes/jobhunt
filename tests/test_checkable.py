"""An ask is actionable when it names something CHECKABLE.

Deciding what counts as a requirement from how RARE a term is inverts on a tech
corpus: Kubernetes, AWS, Terraform, Go and Java appear in many postings precisely
because they matter, so frequency classified them as boilerplate and dropped them
from the ask — while "societal impacts and ethics", being rare, survived. On the
brex posting every hard requirement came back matched with nothing unmet.

Frequency is a bad proxy for importance exactly when the common things are the
important ones. What separates the two classes is not rarity but whether the ask
names something you can check: a technology or proper noun, a quantity of years,
a credential. A disposition — strong communication, high standards, cares about
impact — is not checkable and is not a gap.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import tailor

BREX = [
    "7+ years of professional experience designing, building, and operating backend "
    "or infrastructure systems in production",
    "Strong proficiency in backend programming languages (e.g., Go, Java, Kotlin, or "
    "Python) with a focus on reliability and performance",
    "Experience architecting and operating scalable, high-availability distributed "
    "systems on cloud platforms (e.g., AWS, GCP, Azure)",
    "Deep familiarity with containerization and orchestration (e.g., Docker, "
    "Kubernetes) and infrastructure-as-code (e.g., Terraform, CloudFormation)",
]
SOFT = [
    "Strong communication and collaboration skills, including writing clear design docs",
    "Care about the societal impacts and ethics of your work",
    "Uphold our high engineering standards",
    "Strong written and verbal English communication",
]


class TechnologyTests(unittest.TestCase):
    def test_a_named_technology_is_checkable(self):
        found = tailor.checkable(BREX[3])["tech"]
        self.assertIn("kubernetes", found)
        self.assertIn("terraform", found)

    def test_several_named_languages_are_all_captured(self):
        found = tailor.checkable(BREX[1])["tech"]
        for lang in ("go", "java", "kotlin", "python"):
            self.assertIn(lang, found)

    def test_an_acronym_is_checkable(self):
        found = tailor.checkable(BREX[2])["tech"]
        self.assertIn("aws", found)
        self.assertIn("gcp", found)

    def test_a_sentence_opening_word_is_not_a_technology(self):
        self.assertNotIn("deep", tailor.checkable(BREX[3])["tech"])
        self.assertNotIn("experience", tailor.checkable(BREX[2])["tech"])

    def test_a_disposition_names_no_technology(self):
        for req in SOFT:
            self.assertEqual(tailor.checkable(req)["tech"], set(), req)

    def test_a_language_name_is_not_mistaken_for_a_technology(self):
        self.assertNotIn("english", tailor.checkable(SOFT[3])["tech"])


class YearsTests(unittest.TestCase):
    def test_a_years_requirement_is_read(self):
        self.assertEqual(tailor.checkable(BREX[0])["years"], 7)

    def test_a_plain_years_phrasing_is_read(self):
        self.assertEqual(tailor.checkable("5 years of backend experience")["years"], 5)

    def test_a_requirement_with_no_quantity_reads_none(self):
        self.assertIsNone(tailor.checkable(BREX[1])["years"])

    def test_a_version_number_is_not_a_year_count(self):
        self.assertIsNone(tailor.checkable("Experience with Python 3 and Rails 7")["years"])


class ActionableTests(unittest.TestCase):
    def test_a_requirement_naming_nothing_checkable_is_not_a_gap(self):
        for req in SOFT:
            self.assertFalse(tailor.is_actionable(req), req)

    def test_every_hard_brex_requirement_is_actionable(self):
        for req in BREX:
            self.assertTrue(tailor.is_actionable(req), req)


class BrexAcceptanceTests(unittest.TestCase):
    """The test to hold to: these four must not come back silently covered."""

    FACTS = {  # noqa: RUF012
        "skill_groups": [{"name": "Backend", "terms": ["ruby", "rails", "postgres",
                                                       "python", "docker", "sidekiq"]}],
        "roles": [{"company": "x", "title": "Eng",
                   "start": "2021-10", "end": "present",
                   "bullets": [{"text": "Built Rails services on Postgres with Docker",
                                "weight": 9}]}],
        "projects": [],
    }

    def outcomes(self):
        matched, gaps = tailor.evidence(BREX, self.FACTS, years_of_experience=5)
        by_req = {m["requirement"]: m for m in matched}
        return by_req, gaps

    def test_the_years_requirement_is_not_reported_as_met(self):
        by_req, gaps = self.outcomes()
        entry = by_req.get(BREX[0])
        self.assertTrue(BREX[0] in gaps or (entry and entry.get("partial")),
                        "7+ years reported as met against five")

    def test_the_unmet_years_are_named(self):
        by_req, _ = self.outcomes()
        entry = by_req.get(BREX[0])
        if entry:
            self.assertTrue(any("year" in m for m in entry.get("missing", [])))

    def test_kubernetes_and_terraform_are_reported_unmet(self):
        by_req, gaps = self.outcomes()
        entry = by_req.get(BREX[3])
        missing = " ".join(entry.get("missing", [])) if entry else ""
        self.assertTrue(BREX[3] in gaps or "kubernetes" in missing, "kubernetes read as met")
        self.assertTrue(BREX[3] in gaps or "terraform" in missing, "terraform read as met")

    def test_the_cloud_platforms_are_reported_unmet(self):
        by_req, gaps = self.outcomes()
        entry = by_req.get(BREX[2])
        missing = " ".join(entry.get("missing", [])) if entry else ""
        self.assertTrue(BREX[2] in gaps or "aws" in missing, "AWS read as met")

    def test_docker_which_he_does_have_is_not_reported_unmet(self):
        by_req, _ = self.outcomes()
        entry = by_req.get(BREX[3])
        if entry:
            self.assertNotIn("docker", entry.get("missing", []))

    def test_python_which_he_does_have_is_not_reported_unmet(self):
        by_req, _ = self.outcomes()
        entry = by_req.get(BREX[1])
        if entry:
            self.assertNotIn("python", entry.get("missing", []))


if __name__ == "__main__":
    unittest.main()
