"""Two-letter technologies must survive tokenising, or they can never match.

The evidence side drops any token of two characters or fewer, while checkable()
keeps "ai" as a tech term from a requirement. So a posting asking for practical
AI experience reported a gap no wording could close — measured on GitLab's "AI
Fluency" and on three of OPENLANE's Must Have's, against a resume whose leading
project is five AI coding agents.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import tailor


class ShortTechSurvivesTokenising(unittest.TestCase):
    def test_ai_is_kept(self):
        self.assertIn("ai", tailor._terms("Five AI coding agents reviewing what the AI produces"))

    def test_an_ai_requirement_is_answered_by_ai_evidence(self):
        req = ["AI Fluency: Practical experience with AI coding tools."]
        facts = {"roles": [], "projects": [
            {"name": "FPS", "text": "Five AI coding agents running against one repository."}]}
        matched, gaps = tailor.evidence(req, facts)
        self.assertEqual(gaps, [], f"unmatchable: {gaps}")

    def test_ordinary_two_letter_words_are_still_dropped(self):
        toks = tailor._terms("we go to it if we do so as an my by")
        self.assertNotIn("go", toks, "'go' is the verb far more often than the language here")
        for w in ("to", "it", "if", "do", "so", "as", "an", "my", "by"):
            self.assertNotIn(w, toks)


if __name__ == "__main__":
    unittest.main()
