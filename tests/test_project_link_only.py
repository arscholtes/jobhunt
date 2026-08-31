"""A project may be a bare name and link, with no description.

The resume points at the repo; the README is the description. The renderer
hardcoded ": {text}", so an entry with no text rendered a dangling colon.
"""

import unittest

from jobhunt import resume
from tests.test_projects_present import DOMAINS, SHAPES


def _doc(**over):
    p = {"name": "FPS", "url": "https://github.com/arscholtes/fps",
         "text": "", "shapes": [], "domains": [], "weight": 9}
    p.update(over)
    return {"me": {"name": "A"}, "summary": "", "roles": [], "projects": [p],
            "education": {"show": False, "lines": []}, "skills": []}


class LinkOnlyProject(unittest.TestCase):
    def test_no_dangling_colon_when_text_is_empty(self):
        line = next(x for x in resume.render(_doc()).splitlines() if x.startswith("- FPS"))
        self.assertNotIn(": ", line, f"dangling separator: {line!r}")
        self.assertTrue(line.rstrip().endswith(")"), line)

    def test_name_and_url_both_survive(self):
        out = resume.render(_doc())
        self.assertIn("FPS", out)
        self.assertIn("https://github.com/arscholtes/fps", out)

    def test_described_project_still_renders_its_text(self):
        out = resume.render(_doc(name="jobhunt", text="Polls ATS feeds."))
        self.assertIn("- jobhunt (https://github.com/arscholtes/fps): Polls ATS feeds.", out)

    def test_no_url_and_no_text_renders_just_the_name(self):
        self.assertIn("- FPS", resume.render(_doc(url="")))
        self.assertNotIn("FPS ()", resume.render(_doc(url="")))


class FpsInEveryVariant(unittest.TestCase):
    """ANY/ANY tags: FPS is the strongest AI-domain signal, so it must not filter out."""

    def test_fps_reaches_every_shape_and_domain(self):
        facts = resume.load()
        names = {p["name"] for p in facts["projects"]}
        self.assertIn("FPS", names, "FPS missing from resume.toml")
        missing = [
            f"{shape}.{domain}"
            for shape in SHAPES for domain in DOMAINS
            if "FPS" not in {p["name"] for p in resume._projects(facts, shape, domain)}
        ]
        self.assertEqual([], missing, f"FPS filtered out of: {missing}")


if __name__ == "__main__":
    unittest.main()
