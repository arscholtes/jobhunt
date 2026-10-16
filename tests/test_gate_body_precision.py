"""A phrase precise enough for a title can be ordinary prose in a body.

Same failure as REGION_LOCK vs REGION_LOCK_TAG: a pattern written to read a
title, matched against a description, fires on wording that means nothing about
the role. Measured on a real OPENLANE marketplace posting, which names backend
development three times and got the forward-deployed resume — which then
withheld every backend, fullstack and platform bullet it had.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import gate

# Trimmed from the real posting, keeping only the wording each assertion needs.
MARKETPLACE_BODY = (
    "We're hiring AI-first Sr. Software Engineers to build, evolve, and scale "
    "our U.S. marketplace platforms. Backend development (Java, Kotlin, Go, "
    "Python, .NET, Ruby, or similar). Comfort working in modern CI/CD "
    "environments. Partner with Product to translate business needs into "
    "durable, scalable technical solutions. Embed AI-driven capabilities into "
    "marketplace features. Use AI tools to accelerate coding and testing. "
    "Actively uses AI development tools (code copilots, AI debuggers)."
)


class TitlePhrasesDoNotDecideShapeFromABody(unittest.TestCase):
    def test_ordinary_technical_solutions_prose_is_not_a_forward_deployed_role(self):
        shape, _, reasons, _ = gate.classify(
            {"title": "Sr. Software Engineer (AI First)", "description": MARKETPLACE_BODY})
        self.assertNotEqual(shape, "fde", f"fde won from body prose: {reasons}")
        self.assertEqual(shape, "backend", reasons)

    def test_the_phrase_still_names_the_role_when_it_is_in_the_title(self):
        shape, _, reasons, _ = gate.classify(
            {"title": "Technical Solutions Engineer", "description": "Anything at all."})
        self.assertEqual(shape, "fde", reasons)


class PlainAiLanguageIsAnAiDomain(unittest.TestCase):
    def test_a_posting_saying_ai_first_and_ai_driven_reads_as_ai(self):
        _, domain, reasons, _ = gate.classify(
            {"title": "Sr. Software Engineer (AI First)", "description": MARKETPLACE_BODY})
        self.assertEqual(domain, "ai", f"domain came from the wrong signal: {reasons}")


if __name__ == "__main__":
    unittest.main()
