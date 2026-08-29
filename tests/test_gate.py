"""Role-shape classification, and the catch-all that used to swallow the fallback."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import gate


class GenericTitleFallsThroughToBody(unittest.TestCase):
    """A title whose only shape match is the catch-all is not a real match.

    'Senior Software Engineer, <team>' names an engineering job and nothing more.
    The body is the only place a shape can come from, and the catch-all entry in
    SHAPES was satisfying the title lookup and skipping that fallback entirely.
    """

    def test_plain_engineer_title_takes_its_shape_from_the_body(self):
        shape, _, reasons = gate.classify({
            "title": "Senior Software Engineer, Autonomous Freight Systems",
            "description": "You will own backend services and server-side pipelines.",
        })
        self.assertEqual(shape, "backend")
        self.assertTrue(any("body term" in r for r in reasons), reasons)

    def test_a_specific_title_still_wins_over_the_body(self):
        shape, _, _ = gate.classify({
            "title": "Backend Engineer, Payments",
            "description": "Front-end work in React across the whole surface.",
        })
        self.assertEqual(shape, "backend")

    def test_generic_survives_when_the_body_says_nothing_either(self):
        shape, _, _ = gate.classify({
            "title": "Senior Software Engineer, Growth",
            "description": "You will ship things that matter to customers.",
        })
        self.assertEqual(shape, "generic")


if __name__ == "__main__":
    unittest.main()
