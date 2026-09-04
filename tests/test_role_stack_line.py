"""A role may name the platform it sat in, separately from what the person did.

The distinction matters on a resume and was being lost. Bullets are claims of
authorship; the stack a role ran on is context. Collapsing the two turned
"the platform had OpenTelemetry" into "I built the observability", which is the
kind of claim a reader is entitled to test in an interview.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import resume

ROLE = {
    "company": "Acme", "title": "Software Engineer", "kind": "employment",
    "start": "2026-03", "end": "2026-08", "location": "Remote",
    "stack": "Rails 7.2, PostgreSQL, Sidekiq, OpenTelemetry.",
    "bullets": [{"text": "Built the ticketing surface.", "shapes": [], "domains": [], "weight": 9}],
}


class RoleStackLine(unittest.TestCase):
    def _render(self, role):
        facts = {**resume.load(), "roles": [role]}
        return resume.render(resume.build(facts, "backend", "general"))

    def test_the_stack_line_renders_under_the_dates(self):
        out = self._render(ROLE)
        self.assertIn("Rails 7.2, PostgreSQL, Sidekiq, OpenTelemetry.", out)
        lines = out.splitlines()
        stack_at = next(i for i, line in enumerate(lines) if "OpenTelemetry" in line)
        bullet_at = next(i for i, line in enumerate(lines) if line.startswith("- Built the ticketing"))
        self.assertLess(stack_at, bullet_at, "the stack is context and belongs above the claims")

    def test_it_is_not_a_bullet(self):
        out = self._render(ROLE)
        self.assertNotIn("- Rails 7.2", out, "context must not render as a claim")

    def test_a_role_without_one_renders_unchanged(self):
        out = self._render({k: v for k, v in ROLE.items() if k != "stack"})
        self.assertIn("- Built the ticketing surface.", out)
        self.assertNotIn("OpenTelemetry", out)


if __name__ == "__main__":
    unittest.main()
