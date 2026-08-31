"""What the top-scoring postings actually ask for.

Mentor needs the live market, not a snapshot: which of the profile's skills the
best matches keep demanding, which are weighted for and never asked about, and
which terms keep appearing that the profile has no opinion on at all.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import requirements as req


def profile(**over):
    base = {"skills": {"ruby": 5, "rails": 5, "postgres": 3, "cobol": 4}}
    base.update(over)
    return base


def posting(description, title="Backend Engineer", company="co"):
    return {"title": title, "description": description, "company": company}


class DemandTests(unittest.TestCase):
    def test_a_skill_every_posting_asks_for_is_counted_for_all_of_them(self):
        rows = [posting("we use ruby")] * 3
        out = req.summarise(rows, profile())
        self.assertEqual({d["term"]: d["count"] for d in out["demanded"]}["ruby"], 3)

    def test_demand_is_ordered_most_asked_first(self):
        rows = [posting("ruby and rails"), posting("ruby"), posting("ruby")]
        terms = [d["term"] for d in req.summarise(rows, profile())["demanded"]]
        self.assertEqual(terms[0], "ruby")

    def test_a_skill_nobody_asks_for_is_reported_as_unasked(self):
        rows = [posting("ruby and rails")] * 3
        self.assertIn("cobol", [d["term"] for d in req.summarise(rows, profile())["unasked"]])

    def test_an_unasked_skill_carries_the_weight_being_spent_on_it(self):
        rows = [posting("ruby")] * 3
        entry = next(d for d in req.summarise(rows, profile())["unasked"] if d["term"] == "cobol")
        self.assertEqual(entry["weight"], 4)

    def test_a_skill_that_is_asked_for_is_not_also_reported_unasked(self):
        rows = [posting("ruby")] * 3
        self.assertNotIn("ruby", [d["term"] for d in req.summarise(rows, profile())["unasked"]])

    def test_word_boundaries_stop_a_false_demand(self):
        rows = [posting("we use rubyists")] * 3
        counts = {d["term"]: d["count"] for d in req.summarise(rows, profile())["demanded"]}
        self.assertEqual(counts.get("ruby", 0), 0)

    def test_the_share_of_postings_is_reported_not_just_the_count(self):
        rows = [posting("ruby"), posting("nothing"), posting("nothing"), posting("nothing")]
        entry = next(d for d in req.summarise(rows, profile())["demanded"] if d["term"] == "ruby")
        self.assertAlmostEqual(entry["share"], 0.25, places=2)

    def test_an_empty_corpus_does_not_divide_by_zero(self):
        out = req.summarise([], profile())
        self.assertEqual(out["postings"], 0)


class UnmetTests(unittest.TestCase):
    """Terms the market keeps asking for that the profile has no opinion on."""

    def test_a_frequent_unknown_term_surfaces(self):
        rows = [posting("we run kubernetes in production")] * 5
        self.assertIn("kubernetes", [u["term"] for u in req.summarise(rows, profile())["unmet"]])

    def test_a_term_already_in_the_profile_is_not_unmet(self):
        rows = [posting("we use ruby heavily")] * 5
        self.assertNotIn("ruby", [u["term"] for u in req.summarise(rows, profile())["unmet"]])

    def test_common_english_is_not_mistaken_for_a_requirement(self):
        rows = [posting("you will work with the team and the people")] * 5
        terms = [u["term"] for u in req.summarise(rows, profile())["unmet"]]
        for stop in ("the", "and", "with", "you", "will", "work", "team"):
            self.assertNotIn(stop, terms)

    def test_a_token_carrying_trailing_punctuation_is_normalised(self):
        rows = [posting("we run kubernetes. every day.")] * 5
        terms = [u["term"] for u in req.summarise(rows, profile())["unmet"]]
        self.assertIn("kubernetes", terms)
        self.assertNotIn("kubernetes.", terms)

    def test_url_fragments_are_not_requirements(self):
        rows = [posting("see https example com for details")] * 5
        self.assertNotIn("https", [u["term"] for u in req.summarise(rows, profile())["unmet"]])

    def test_a_simple_plural_is_recognised_as_its_singular(self):
        rows = [posting("we build many apis here")] * 5
        p = profile(skills={"api": 5})
        self.assertNotIn("apis", [u["term"] for u in req.summarise(rows, p)["unmet"]])

    def test_generic_job_advert_prose_is_not_reported_as_a_requirement(self):
        rows = [posting("you will design features, improve core tools and ship at scale")] * 5
        terms = [u["term"] for u in req.summarise(rows, profile())["unmet"]]
        for word in ("design", "features", "improve", "core", "tools", "ship", "scale"):
            self.assertNotIn(word, terms)

    def test_a_real_technology_still_surfaces_through_the_stoplist(self):
        rows = [posting("you will design features using kubernetes at scale")] * 5
        self.assertIn("kubernetes", [u["term"] for u in req.summarise(rows, profile())["unmet"]])

    def test_a_rare_term_does_not_surface(self):
        rows = [posting("kubernetes")] + [posting("nothing here")] * 9
        self.assertNotIn("kubernetes", [u["term"] for u in req.summarise(rows, profile())["unmet"]])

    def test_boilerplate_is_stripped_before_terms_are_counted(self):
        boiler = "We are ExampleCo and we love kubernetes. " * 8
        rows = [posting(boiler + f"role {i}", company="co") for i in range(5)]
        out = req.summarise(rows, profile(), boilerplate={"co": (boiler, "")})
        self.assertNotIn("kubernetes", [u["term"] for u in out["unmet"]])


class RenderTests(unittest.TestCase):
    def test_the_report_names_how_many_postings_it_read(self):
        rows = [posting("ruby")] * 3
        self.assertIn("3", req.render(req.summarise(rows, profile())))

    def test_the_report_shows_an_unasked_skill_so_weight_can_be_moved(self):
        rows = [posting("ruby")] * 3
        self.assertIn("cobol", req.render(req.summarise(rows, profile())))

    def test_an_empty_corpus_renders_a_sentence_rather_than_crashing(self):
        self.assertIsInstance(req.render(req.summarise([], profile())), str)


if __name__ == "__main__":
    unittest.main()
