"""Fit scoring, and the per-company boilerplate that distorts it."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import score as score_mod


def profile(**over):
    base = {
        "search": {"titles": ["backend engineer"], "exclude_titles": ["intern"],
                   "locations": ["remote"], "remote_only": False, "elsewhere_weight": 0.3},
        "skills": {"ruby": 5, "rails": 5, "postgres": 3, "kubernetes": 2, "go": 2, "terraform": 1},
        "interests": {"developer tools": 3},
        "dealbreakers": [{"pattern": "security clearance", "why": "no"}],
    }
    base.update(over)
    return base


def job(title="Backend Engineer", description="", **over):
    base = {"id": "src:co:1", "title": title, "description": description,
            "location": "Remote", "remote": 1, "company": "co"}
    base.update(over)
    return base


class DealbreakerTests(unittest.TestCase):
    def test_a_clean_posting_has_no_dealbreaker(self):
        self.assertIsNone(score_mod.dealbreaker(job(), profile()))

    def test_a_dealbreaker_pattern_in_the_body_disqualifies(self):
        self.assertIsNotNone(score_mod.dealbreaker(job(description="requires a security clearance"), profile()))

    def test_the_reason_names_the_pattern(self):
        reason = score_mod.dealbreaker(job(description="requires a security clearance"), profile())
        self.assertIn("security clearance", reason)

    def test_a_pattern_containing_punctuation_still_fires(self):
        """The pattern is normalised the same way the haystack is.

        _terms() drops every character outside [a-z0-9+#. -], so a dealbreaker
        written naturally as "on-call 24/7" used to be compared against a haystack
        reading "on-call 24 7" and silently never fired. A rule nobody can tell is
        broken is worse than no rule.
        """
        p = profile(dealbreakers=[{"pattern": "on-call 24/7", "why": "no"}])
        self.assertIsNotNone(score_mod.dealbreaker(job(description="on-call 24/7 rotation"), p))

    def test_an_excluded_title_containing_punctuation_still_fires(self):
        p = profile()
        p["search"]["exclude_titles"] = ["c/c++"]
        self.assertIsNotNone(score_mod.dealbreaker(job(title="C/C++ Systems Engineer"), p))

    def test_normalising_the_pattern_does_not_make_it_match_everything(self):
        p = profile(dealbreakers=[{"pattern": "on-call 24/7", "why": "no"}])
        self.assertIsNone(score_mod.dealbreaker(job(description="a pleasant role"), p))

    def test_an_excluded_title_disqualifies_by_prefix(self):
        self.assertIsNotNone(score_mod.dealbreaker(job(title="Software Engineer Internship"), profile()))

    def test_an_excluded_title_word_in_the_body_does_not_disqualify(self):
        # exclude_titles is a title rule; a body mentioning interns is not one.
        self.assertIsNone(score_mod.dealbreaker(job(description="we host interns each summer"), profile()))


class EarlyCareerExclusionTests(unittest.TestCase):
    """Early-career postings were ranking near the top of a senior's shortlist.

    "Software Engineer, New Grad (Dec 2026)" scored 92.0, third overall. The title
    reads as a plain engineering role to every weight in the model, so nothing
    below the title rule can catch it.
    """

    def profile_with_early_career(self):
        p = profile()
        p["search"]["exclude_titles"] = ["intern", "new grad", "early career", "junior",
                                         "principal", "staff", "manager", "director"]
        return p

    def test_a_new_grad_title_is_excluded(self):
        j = job(title="Software Engineer, New Grad (Dec 2026)")
        self.assertIsNotNone(score_mod.dealbreaker(j, self.profile_with_early_career()))

    def test_an_early_career_title_is_excluded(self):
        j = job(title="Software Engineer, Early Career (AI)")
        self.assertIsNotNone(score_mod.dealbreaker(j, self.profile_with_early_career()))

    def test_a_junior_title_is_excluded(self):
        j = job(title="Junior Software Engineer")
        self.assertIsNotNone(score_mod.dealbreaker(j, self.profile_with_early_career()))

    def test_a_plural_new_grads_title_is_caught_by_the_prefix_match(self):
        j = job(title="Software Engineer (New Grads)")
        self.assertIsNotNone(score_mod.dealbreaker(j, self.profile_with_early_career()))

    def test_a_senior_title_is_untouched(self):
        j = job(title="Senior Backend Engineer")
        self.assertIsNone(score_mod.dealbreaker(j, self.profile_with_early_career()))

    def test_early_career_language_in_the_body_does_not_exclude(self):
        # exclude_titles is a title rule. A posting that merely mentions a new-grad
        # programme is not itself an early-career role.
        j = job(title="Senior Backend Engineer", description="We also hire new grads.")
        self.assertIsNone(score_mod.dealbreaker(j, self.profile_with_early_career()))

    def test_the_reason_names_which_title_term_matched(self):
        j = job(title="Software Engineer, New Grad (Dec 2026)")
        reason = score_mod.dealbreaker(j, self.profile_with_early_career())
        self.assertIn("new grad", reason)


class ScoreTests(unittest.TestCase):
    def test_a_matching_title_earns_the_title_weight(self):
        _, out = score_mod.score(job(title="Backend Engineer"), profile())
        self.assertEqual(out["title"], score_mod.WEIGHTS["title"])

    def test_a_non_matching_title_earns_nothing(self):
        _, out = score_mod.score(job(title="Marketing Lead"), profile())
        self.assertEqual(out["title"], 0)

    def test_matched_skills_are_reported_for_auditability(self):
        _, out = score_mod.score(job(description="ruby and rails and postgres"), profile())
        self.assertIn("ruby", out["skills_matched"])

    def test_remote_earns_the_full_location_weight(self):
        _, out = score_mod.score(job(remote=1), profile())
        self.assertEqual(out["location"], score_mod.WEIGHTS["location"])

    def test_elsewhere_onsite_is_a_preference_not_a_filter(self):
        _, out = score_mod.score(job(remote=0, location="Des Moines"), profile())
        self.assertGreater(out["location"], 0)

    def test_remote_only_zeroes_an_onsite_posting(self):
        p = profile()
        p["search"]["remote_only"] = True
        _, out = score_mod.score(job(remote=0, location="Des Moines"), p)
        self.assertEqual(out["location"], 0)

    def test_the_total_never_goes_below_zero(self):
        total, _ = score_mod.score(job(title="Marketing Lead", remote=0, location="Nowhere"),
                                   dict(profile(), skills={}, interests={}))
        self.assertGreaterEqual(total, 0.0)

    def test_a_word_boundary_stops_a_false_skill_match(self):
        _, out = score_mod.score(job(description="we use gorillas"), profile())
        self.assertNotIn("go", out.get("skills_matched", []))


class BoilerplateStrippingTests(unittest.TestCase):
    """The measured top accuracy defect.

    A company that repeats its whole stack on every posting hands each role every
    skill it names. GitLab ships 1,483 identical characters on all 219 of its
    postings, which is how an EMEA-only field role scored a perfect 40.0/40 on
    skills while a genuine backend role scored 56.7 and was never emailed.
    """

    BOILER = ("At ExampleCo we build with Ruby, Rails, Postgres, Kubernetes, Go and "
              "Terraform across a distributed team. " * 4)

    def test_boilerplate_is_stripped_before_terms_are_read(self):
        stripped = score_mod.strip_boilerplate(self.BOILER + "The role: write copy.", self.BOILER)
        self.assertNotIn("kubernetes", stripped.lower())

    def test_stripping_keeps_the_role_specific_remainder(self):
        stripped = score_mod.strip_boilerplate(self.BOILER + "The role: write copy.", self.BOILER)
        self.assertIn("write copy", stripped)

    def test_stripping_with_no_boilerplate_is_a_no_op(self):
        self.assertEqual(score_mod.strip_boilerplate("a description", ""), "a description")

    def test_stripping_a_prefix_that_does_not_match_leaves_the_text_alone(self):
        self.assertEqual(score_mod.strip_boilerplate("a description", "something else"), "a description")

    def test_a_none_description_survives_stripping(self):
        self.assertEqual(score_mod.strip_boilerplate(None, self.BOILER), "")

    def test_a_role_inheriting_only_boilerplate_skills_scores_lower_than_a_real_match(self):
        p = profile()
        field = job(title="Field Engineer", description=self.BOILER + " Travel to customer sites.")
        backend = job(title="Backend Engineer", description="We write Ruby and Rails against Postgres.")

        field_total, _ = score_mod.score(field, p, boilerplate=self.BOILER)
        backend_total, _ = score_mod.score(backend, p, boilerplate=self.BOILER)
        self.assertLess(field_total, backend_total)

    def test_without_stripping_the_boilerplate_role_wins_which_is_the_bug(self):
        p = profile()
        field = job(title="Field Engineer", description=self.BOILER + " Travel to customer sites.")
        unstripped, _ = score_mod.score(field, p)
        stripped, _ = score_mod.score(field, p, boilerplate=self.BOILER)
        self.assertLess(stripped, unstripped)

    def test_scoring_without_a_boilerplate_argument_still_works(self):
        total, _ = score_mod.score(job(description="ruby"), profile())
        self.assertGreater(total, 0)

    def test_the_title_is_never_stripped_even_if_it_repeats_the_boilerplate(self):
        # Boilerplate is a description artifact; the title is always role-specific.
        p = profile()
        _, out = score_mod.score(job(title="Backend Engineer", description=self.BOILER),
                                 p, boilerplate=self.BOILER)
        self.assertEqual(out["title"], score_mod.WEIGHTS["title"])


if __name__ == "__main__":
    unittest.main()
