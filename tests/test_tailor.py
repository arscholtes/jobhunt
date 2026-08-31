"""Per-posting tailoring, and the brief written from it.

gate.py picks one of twenty pre-built shape.domain variants. That is variant
SELECTION. Tailoring ranks this candidate's material against THIS posting's
language, which is a different question and had never been asked.

Two constraints carried in from what already exists and must not regress:

  relevance decides which bullets survive; authoring order decides the sequence
  they are read in, because a role that opens with its trophy reads incoherently

  weight outranks relevance, because an earlier version's flat relevance bonus
  let three tagged weight-8 bullets push out an untagged weight-10 one — the
  posting's vocabulary overruling his own judgment of his best material
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import ClassVar

from jobhunt import tailor


def posting(description="", title="Senior Backend Engineer", company="acme"):
    return {"id": "s:acme:1", "title": title, "company": company, "url": "http://x",
            "description": description, "location": "Remote", "remote": 1}


def bullet(text, weight=5, shapes=None, domains=None):
    b = {"text": text, "weight": weight}
    if shapes:
        b["shapes"] = shapes
    if domains:
        b["domains"] = domains
    return b


class RelevanceTests(unittest.TestCase):
    def test_a_bullet_sharing_language_with_the_posting_scores_higher(self):
        post = posting("We run Rails and Postgres at scale.")
        near = tailor.relevance(bullet("Rebuilt the Rails billing pipeline"), post)
        far = tailor.relevance(bullet("Wrote a Swift animation layer"), post)
        self.assertGreater(near, far)

    def test_relevance_is_zero_when_nothing_overlaps(self):
        self.assertEqual(tailor.relevance(bullet("Swift animations"), posting("Rails only")), 0)

    def test_common_english_does_not_create_relevance(self):
        post = posting("You will work with the team on the product.")
        self.assertEqual(tailor.relevance(bullet("Worked with a team on a product"), post), 0)

    def test_the_posting_title_counts_as_its_language(self):
        post = posting("", title="Staff Rails Engineer")
        self.assertGreater(tailor.relevance(bullet("Ten years of Rails"), post), 0)

    def test_a_bullet_with_no_text_scores_zero_rather_than_raising(self):
        self.assertEqual(tailor.relevance({"weight": 5}, posting("Rails")), 0)


class RankingTests(unittest.TestCase):
    """Weight first. The posting refines the order; it does not overrule him."""

    def test_a_heavier_bullet_outranks_a_more_relevant_lighter_one(self):
        post = posting("Kubernetes Kubernetes Kubernetes")
        best = bullet("Founded the platform team", weight=10)
        noisy = bullet("Ran Kubernetes", weight=8)
        picked = tailor.select([noisy, best], post, limit=1)
        self.assertEqual(picked[0]["text"], "Founded the platform team")

    def test_relevance_breaks_a_tie_between_equal_weights(self):
        post = posting("We run Rails.")
        picked = tailor.select([bullet("Swift work", 8), bullet("Rails work", 8)], post, limit=1)
        self.assertEqual(picked[0]["text"], "Rails work")

    def test_survivors_are_returned_in_authoring_order(self):
        # The rule that already exists and must not regress: rank decides who
        # survives, the author decides the sequence.
        post = posting("Rails")
        items = [bullet("first, Rails", 8), bullet("second", 9), bullet("third, Rails", 8)]
        picked = tailor.select(items, post, limit=2)
        self.assertEqual([p["text"] for p in picked], ["first, Rails", "second"])

    def test_a_shape_or_domain_tag_still_gates_eligibility(self):
        post = posting("Rails")
        items = [bullet("backend only", 9, shapes=["backend"])]
        self.assertEqual(tailor.select(items, post, shape="fde", limit=5), [])

    def test_an_untagged_bullet_remains_eligible_everywhere(self):
        post = posting("Rails")
        self.assertEqual(len(tailor.select([bullet("anywhere", 9)], post, shape="fde", limit=5)), 1)


class RequirementTests(unittest.TestCase):
    DESC = """About us
    We are a company.

    Requirements:
    - 5+ years of Ruby on Rails experience
    - Strong PostgreSQL and query optimisation
    - Experience with Kubernetes in production

    Nice to have:
    - Elixir
    """

    def test_requirement_lines_are_extracted(self):
        reqs = tailor.requirements(posting(self.DESC))
        self.assertTrue(any("Rails" in r for r in reqs))

    def test_prose_outside_a_requirement_list_is_not_a_requirement(self):
        reqs = tailor.requirements(posting(self.DESC))
        self.assertFalse(any("We are a company" in r for r in reqs))

    def test_a_posting_with_no_list_yields_nothing_rather_than_guessing(self):
        self.assertEqual(tailor.requirements(posting("We want someone great.")), [])

    def test_requirements_are_deduplicated(self):
        d = "Requirements:\n- Ruby\n- Ruby\n"
        self.assertEqual(len(tailor.requirements(posting(d))), 1)


class HtmlRequirementTests(unittest.TestCase):
    """The corpus stores HTML, not markdown.

    The first version of the extractor looked for "- " lines and found
    requirements in 0 of 192 high-scoring postings, because every board serves
    <h3> headings and <li> items. A parser written against a format the data does
    not use returns an empty gap list, which reads exactly like "you match
    everything".
    """

    HTML = ("<h2>About us</h2><p>We are a company.</p>"
            "<h3>What you&#39;ll need</h3><ul>"
            "<li>5+ years of Ruby on Rails</li>"
            "<li>Strong PostgreSQL and query optimisation</li>"
            "</ul>"
            "<h3>Benefits</h3><ul><li>Dental</li></ul>")

    def test_requirements_are_extracted_from_html_lists(self):
        reqs = tailor.requirements(posting(self.HTML))
        self.assertTrue(any("Rails" in r for r in reqs))

    def test_html_tags_do_not_survive_into_the_requirement(self):
        for r in tailor.requirements(posting(self.HTML)):
            self.assertNotIn("<", r)

    def test_entities_are_decoded(self):
        reqs = tailor.requirements(posting(self.HTML))
        self.assertFalse(any("&#39;" in r for r in reqs))

    def test_a_list_under_an_unrelated_heading_is_not_a_requirement(self):
        # Benefits are not requirements, and treating them as such produces gaps
        # like "no evidence of dental".
        self.assertFalse(any("Dental" in r for r in tailor.requirements(posting(self.HTML))))

    def test_prose_paragraphs_are_not_requirements(self):
        self.assertFalse(any("We are a company" in r
                             for r in tailor.requirements(posting(self.HTML))))


class GapTests(unittest.TestCase):
    """The section that decides whether to apply at all."""

    FACTS: ClassVar = {
        "skill_groups": [{"name": "Backend", "terms": ["ruby", "rails", "postgres"]}],
        "roles": [{"company": "x", "title": "Eng", "bullets": [
            {"text": "Scaled Rails and Postgres for a multi-tenant platform", "weight": 9}]}],
        "projects": [],
    }

    def test_a_requirement_with_matching_evidence_is_not_a_gap(self):
        matched, gaps = tailor.evidence(["5+ years of Rails"], self.FACTS)
        self.assertEqual(gaps, [])
        self.assertTrue(matched[0]["evidence"])

    def test_a_requirement_with_no_evidence_is_a_gap(self):
        _, gaps = tailor.evidence(["Deep Kubernetes operations experience"], self.FACTS)
        self.assertEqual(len(gaps), 1)

    def test_the_gap_carries_the_requirement_verbatim_so_it_can_be_judged(self):
        _, gaps = tailor.evidence(["Deep Kubernetes operations experience"], self.FACTS)
        self.assertEqual(gaps[0], "Deep Kubernetes operations experience")

    def test_evidence_names_where_it_came_from(self):
        matched, _ = tailor.evidence(["Rails experience"], self.FACTS)
        self.assertTrue(any("Rails" in e for e in matched[0]["evidence"]))

    def test_a_skill_term_alone_counts_as_evidence(self):
        _, gaps = tailor.evidence(["PostgreSQL tuning"], self.FACTS)
        self.assertEqual(gaps, [])

    def test_no_requirements_means_no_gaps_rather_than_everything_being_a_gap(self):
        matched, gaps = tailor.evidence([], self.FACTS)
        self.assertEqual((matched, gaps), ([], []))


class BudgetTests(unittest.TestCase):
    """A brief that reprints the whole resume has removed no tedium.

    The first run against a real posting emitted twenty bullets across five roles,
    including an esports division-manager role for a reinforcement-learning job.
    The point is a page he reads instead of re-reading the posting; a second copy
    of his resume is not that.
    """

    def roles(self):
        return [
            {"company": "A", "title": "Eng", "bullets": [
                bullet("Rails and Postgres at scale", 9),
                bullet("Hotwire and Turbo frames", 8)]},
            {"company": "B", "title": "Founder", "bullets": [
                bullet("Ran an esports organisation", 7),
                bullet("Won a league title", 6)]},
        ]

    def test_the_total_number_of_bullets_is_bounded(self):
        picked = tailor.bullets_for(self.roles(), posting("Rails"), budget=3)
        self.assertLessEqual(sum(len(b) for _, _, b in picked), 3)

    def test_the_budget_goes_to_the_roles_this_posting_cares_about(self):
        picked = tailor.bullets_for(self.roles(), posting("Rails Postgres Hotwire"), budget=2)
        self.assertEqual(picked[0][0], "A")

    def test_a_role_with_nothing_relevant_is_kept_with_fewer_bullets(self):
        """Superseded by a correctness decision, and the old assertion is the bug.

        This used to assert that an irrelevant role was DROPPED. Dropping it
        removes an employer from the work history, which on an application form
        misstates it and manufactures a gap. A role may be trimmed to nothing;
        it may not disappear.
        """
        picked = tailor.bullets_for(self.roles(), posting("Rails Postgres Hotwire"), budget=2)
        self.assertIn("B", [c for c, _, _ in picked])

    def test_a_long_irrelevant_role_does_not_outrank_a_short_relevant_one(self):
        """Summing relevance rewards verbosity, not fit.

        On the first real run this put two esports roles above the engineering
        ones for a reinforcement-learning job, purely because they had more
        bullets. A role's claim on the page is how well its best material speaks
        to the posting, not how much of it there is.
        """
        roles = [
            {"company": "Eng", "title": "Engineer", "bullets": [
                bullet("Rails Postgres Hotwire Sidekiq", 9)]},
            {"company": "Other", "title": "Founder", "bullets": [
                bullet("Ran an organisation", 7), bullet("Won a title", 7),
                bullet("Recruited people", 7), bullet("Handled sponsorship", 7),
                bullet("Managed rosters", 7), bullet("Ran tournaments", 7)]},
        ]
        picked = tailor.bullets_for(roles, posting("Rails Postgres Hotwire Sidekiq"), budget=3)
        self.assertEqual(picked[0][0], "Eng")

    def test_roles_are_returned_in_their_original_order(self):
        picked = tailor.bullets_for(self.roles(), posting("Rails esports"), budget=4)
        self.assertEqual([c for c, _, _ in picked], ["A", "B"])

    def test_bullets_within_a_role_stay_in_authoring_order(self):
        # Budget is shared across roles now, so a wider one is needed before a
        # single role holds two bullets.
        picked = tailor.bullets_for(self.roles(), posting("Hotwire Rails"), budget=6)
        self.assertEqual([b["text"] for b in picked[0][2]],
                         ["Rails and Postgres at scale", "Hotwire and Turbo frames"])


class WithheldTests(unittest.TestCase):
    """When the variant gate hides material, say so.

    Found on real data: seven of ten Liftify bullets are tagged backend/platform,
    so a fullstack variant cannot see them, and two broadly-tagged esports roles
    won the page for a reinforcement-learning job by default. The tagging is his
    to decide — but the brief silently showing the wrong roles, with no hint that
    the best ones were filtered out, is the tool making that decision for him.
    """

    def roles(self):
        return [{"company": "Eng", "title": "Engineer", "bullets": [
            bullet("Rails and Postgres at scale", 9, shapes=["backend"]),
            bullet("Sidekiq pipelines", 9, shapes=["backend"]),
            bullet("Some frontend", 6, shapes=["fullstack"])]}]

    def test_material_hidden_by_the_variant_is_counted(self):
        held = tailor.withheld(self.roles(), shape="fullstack", domain="ai")
        self.assertEqual(held[0]["hidden"], 2)

    def test_a_role_losing_nothing_is_not_reported(self):
        roles = [{"company": "X", "title": "E", "bullets": [bullet("anything", 9)]}]
        self.assertEqual(tailor.withheld(roles, shape="fullstack", domain="ai"), [])

    def test_the_report_names_the_tags_that_did_the_filtering(self):
        held = tailor.withheld(self.roles(), shape="fullstack", domain="ai")
        self.assertIn("backend", held[0]["tags"])

    def test_the_brief_mentions_withheld_material(self):
        facts = {"skill_groups": [], "projects": [], "roles": self.roles()}
        out = tailor.brief(posting("Requirements:\n- Rails\n"), facts,
                           {"variant": "fullstack.ai", "shape": "fullstack",
                            "domain": "ai", "reasons": [], "flags": []})
        self.assertIn("withheld", out.lower())


class FrictionTests(unittest.TestCase):
    def test_a_greenhouse_url_is_low_friction(self):
        self.assertEqual(tailor.friction("https://job-boards.greenhouse.io/x/jobs/1"), "low")

    def test_a_workday_url_is_high_friction(self):
        url = "https://x.wd1.myworkdayjobs.com/en-US/careers/job/1"
        self.assertEqual(tailor.friction(url), "high")

    def test_an_unknown_host_is_unknown_rather_than_assumed_easy(self):
        self.assertEqual(tailor.friction("https://careers.example.com/apply"), "unknown")


class BriefTests(unittest.TestCase):
    """A page he writes FROM, never prose written for him."""

    FACTS = GapTests.FACTS

    def brief(self, description="Requirements:\n- Rails experience\n- Kubernetes operations\n"):
        return tailor.brief(posting(description), self.FACTS)

    def test_the_brief_names_the_variant_and_why_it_was_chosen(self):
        out = self.brief()
        self.assertIn("variant", out.lower())

    def test_the_gaps_section_is_present_when_there_are_gaps(self):
        self.assertIn("Kubernetes", self.brief())

    def test_the_apply_url_and_its_friction_are_both_given(self):
        out = self.brief()
        self.assertIn("http://x", out)
        self.assertIn("friction", out.lower())

    def test_the_brief_contains_no_generated_prose_to_send(self):
        # Deliberately not a cover letter: generated prose carries a voice that is
        # not his, readers detect it, and the conversion cost is real.
        out = self.brief().lower()
        for tell in ("dear ", "sincerely", "i am writing to", "please find attached"):
            self.assertNotIn(tell, out)

    def test_the_module_has_no_way_to_contact_an_employer(self):
        # The README promises there is no send path. Keeping it absent beats
        # keeping it behind a flag that defaults off.
        source = (Path(__file__).resolve().parent.parent / "jobhunt" / "tailor.py").read_text()
        for forbidden in ("smtplib", "urlopen", "requests", "def send", "def apply", "def submit"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
