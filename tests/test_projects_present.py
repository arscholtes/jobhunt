"""A section may reorder or trim. It must not vanish.

Third instance of one defect family, after Demandwell being tagged out of every
full-stack variant and the founder roles outweighing the engineering ones.

Measured: five variants — every rails-domain one — rendered ZERO projects, so the
whole section disappeared. Betterment is fullstack.rails, so that live packet
carried no projects at all. And the agent-workflow project was tagged
shapes=platform,backend, so it never appeared on a fullstack or fde variant
either; across the four sendable packet shapes only one project ever rendered.

THE TAGGING ERROR IS SEMANTIC. The domain tag describes the TARGET JOB's domain,
not the project's own language. jobhunt being written in Python is not a reason
to withhold it from a Rails posting — a Rails employer reading a stdlib-only
scoring engine with a blind evaluation harness learns exactly what they want to
know.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import resume

SHAPES = ("backend", "fullstack", "platform", "fde", "generic")
DOMAINS = ("ai", "devtools", "rails", "general")


class ProjectsPresentTests(unittest.TestCase):
    def test_every_variant_renders_at_least_one_project(self):
        facts = resume.load()
        for shape in SHAPES:
            for domain in DOMAINS:
                doc = resume.build(facts, shape, domain)
                self.assertTrue(doc["projects"], f"{shape}.{domain} renders no projects")

    def test_a_rails_variant_renders_projects(self):
        facts = resume.load()
        self.assertTrue(resume.build(facts, "fullstack", "rails")["projects"])

    def test_the_agent_workflow_reaches_a_fullstack_variant(self):
        facts = resume.load()
        names = {p["name"] for p in resume.build(facts, "fullstack", "ai")["projects"]}
        self.assertIn("Multi-session agent workflow", names)

    def test_the_fallback_picks_the_highest_weighted_project(self):
        facts = {**resume.load(), "projects": [
            {"name": "Low", "text": "x", "weight": 3, "shapes": ["nothing"]},
            {"name": "High", "text": "y", "weight": 9, "shapes": ["nothing"]},
        ]}
        doc = resume.build(facts, "fullstack", "rails")
        self.assertEqual([p["name"] for p in doc["projects"]], ["High"])

    def test_a_resume_with_no_projects_at_all_renders_no_section(self):
        # The fallback fills an emptied section; it does not invent one.
        facts = {**resume.load(), "projects": []}
        self.assertEqual(resume.build(facts, "fullstack", "rails")["projects"], [])

    def test_the_section_header_never_appears_with_nothing_under_it(self):
        facts = resume.load()
        for shape in SHAPES:
            for domain in DOMAINS:
                text = resume.render(resume.build(facts, shape, domain))
                if "## Projects" in text:
                    after = text.split("## Projects", 1)[1]
                    body = after.split("\n## ", 1)[0].strip()
                    self.assertTrue(body, f"{shape}.{domain} has an empty Projects header")


class NoRewordingTests(unittest.TestCase):
    def test_every_project_keeps_its_text(self):
        for p in resume.load()["projects"]:
            self.assertTrue(p.get("text", "").strip())

    def test_no_project_text_was_truncated(self):
        for p in resume.load()["projects"]:
            self.assertNotIn("…", p["text"])
            self.assertFalse(p["text"].rstrip().endswith("..."))


if __name__ == "__main__":
    unittest.main()
