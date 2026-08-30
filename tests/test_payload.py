"""Two defects visible in the first real digest payload.

Both waste the thing the digest is rationing — his attention — and both were
found by reading an actual dry run rather than by reasoning about the code.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import digest, gate  # noqa: E402


def row(company, title, total, jid=None):
    return {"id": jid or f"{company}:{title}", "company": company,
            "title": title, "total": total, "location": "Remote", "url": "http://x"}


class DedupeTests(unittest.TestCase):
    """One job listed per location must not eat several slots."""

    def test_the_same_role_twice_is_collapsed(self):
        kept, collapsed = digest.dedupe([
            row("intercom", "Forward Deployed Software Engineer", 68.9, "a"),
            row("intercom", "Forward Deployed Software Engineer", 68.9, "b")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(collapsed, 1)

    def test_the_highest_scoring_instance_survives(self):
        kept, _ = digest.dedupe([
            row("intercom", "Senior Product Engineer, AI", 60.0, "low"),
            row("intercom", "Senior Product Engineer, AI", 67.5, "high")])
        self.assertEqual(kept[0]["id"], "high")

    def test_a_seniority_difference_is_a_different_job_and_survives(self):
        """Measured: any threshold loose enough to catch the one real near-duplicate
        also collapsed a level difference and two distinct teams. A collapsed
        posting is invisible, so a false collapse costs more than a missed one."""
        kept, collapsed = digest.dedupe([
            row("robinhood", "Software Engineer, Wallet", 67.4, "a"),
            row("robinhood", "Senior Software Engineer, Wallet", 67.0, "b")])
        self.assertEqual(len(kept), 2)
        self.assertEqual(collapsed, 0)

    def test_a_board_requisition_id_collapses_location_variants(self):
        rows = [dict(row("intercom", "Senior Product Engineer", 67.5, "a"),
                     internal_job_id=2564571, location="Dublin, Ireland"),
                dict(row("intercom", "Senior Product Engineer, AI", 66.1, "b"),
                     internal_job_id=2564571, location="London, England")]
        kept, collapsed = digest.dedupe(rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(collapsed, 1)

    def test_the_collapsed_locations_are_kept_on_the_survivor(self):
        rows = [dict(row("intercom", "Senior Product Engineer", 67.5, "a"),
                     location="Dublin, Ireland"),
                dict(row("intercom", "Senior Product Engineer", 66.1, "b"),
                     location="London, England")]
        kept, _ = digest.dedupe(rows)
        self.assertIn("London, England", kept[0]["also_in"])

    def test_a_trailing_location_does_not_make_it_a_different_job(self):
        kept, _ = digest.dedupe([
            row("brex", "Senior Software Engineer (New York)", 82.0, "a"),
            row("brex", "Senior Software Engineer (San Francisco)", 82.0, "b")])
        self.assertEqual(len(kept), 1)

    def test_genuinely_different_roles_both_survive(self):
        kept, collapsed = digest.dedupe([
            row("intercom", "Forward Deployed Software Engineer", 68.9),
            row("intercom", "Senior Product Engineer, AI", 67.5)])
        self.assertEqual(len(kept), 2)
        self.assertEqual(collapsed, 0)

    def test_the_same_title_at_different_companies_is_not_a_duplicate(self):
        kept, _ = digest.dedupe([
            row("brex", "Senior Software Engineer", 80.0),
            row("mercury", "Senior Software Engineer", 79.0)])
        self.assertEqual(len(kept), 2)

    def test_order_is_preserved_for_what_survives(self):
        kept, _ = digest.dedupe([
            row("a", "One", 90.0), row("b", "Two", 80.0), row("a", "One", 70.0)])
        self.assertEqual([k["company"] for k in kept], ["a", "b"])

    def test_deduping_an_empty_list_is_harmless(self):
        self.assertEqual(digest.dedupe([]), ([], 0))

    def test_dedupe_runs_before_the_cap_so_slots_are_not_wasted(self):
        rows = [row("x", "Same Role", 90.0, "a"), row("x", "Same Role", 89.0, "b"),
                row("y", "Other Role", 70.0, "c")]
        picked, _ = digest.select_with_overflow(rows, bar=0, limit=2)
        self.assertEqual({p["id"] for p in picked}, {"a", "c"})


class RoleShapeTests(unittest.TestCase):
    """The fallback chooses a RESUME; it must not also describe the role.

    gate.classify replaced the shape with its fallback before returning, so a
    frontend posting reported itself as fullstack and nothing downstream could
    tell that six of twenty selected roles were frontend, ML or IT.
    """

    def test_the_raw_role_shape_survives_the_resume_fallback(self):
        d = gate.decide({"title": "Senior Frontend Engineer", "description": "React and CSS"})
        self.assertEqual(d["role_shape"], "frontend")

    def test_the_resume_shape_is_still_the_fallback(self):
        d = gate.decide({"title": "Senior Frontend Engineer", "description": "React and CSS"})
        self.assertEqual(d["shape"], "fullstack")

    def test_a_shape_with_its_own_resume_reports_the_same_for_both(self):
        d = gate.decide({"title": "Senior Backend Engineer", "description": "Rails and Postgres"})
        self.assertEqual(d["role_shape"], d["shape"])

    def test_the_variant_still_uses_the_resume_shape(self):
        d = gate.decide({"title": "Senior Frontend Engineer", "description": "React"})
        self.assertTrue(d["variant"].startswith("fullstack."))

    def test_an_off_target_shape_can_be_recognised_without_being_excluded(self):
        # fde is arguably on target; that is his call, so nothing is hard-excluded.
        self.assertTrue(digest.off_target("frontend", targets={"backend", "fullstack"}))
        self.assertFalse(digest.off_target("backend", targets={"backend", "fullstack"}))

    def test_an_unknown_shape_is_not_called_off_target(self):
        self.assertFalse(digest.off_target(None, targets={"backend"}))


if __name__ == "__main__":
    unittest.main()


class SummaryLineTests(unittest.TestCase):
    """The line must name the shapes that earned the marker, not the target set.

    It printed the complement: "7 of 20 are shapes you are not targeting
    (backend, fde, fullstack, generic, platform)" — every one of which is a
    target. Read literally it says backend roles are off-target, which is the
    opposite of true and the kind of line that erodes trust in the whole digest.
    """

    def test_the_offending_shapes_are_named(self):
        found = digest.summarise_off_target(
            ["frontend", "frontend", "data", "backend"], targets={"backend", "fullstack"})
        self.assertIn("frontend", found["shapes"])
        self.assertIn("data", found["shapes"])

    def test_a_target_shape_is_never_named_as_offending(self):
        found = digest.summarise_off_target(
            ["frontend", "backend"], targets={"backend", "fullstack"})
        self.assertNotIn("backend", found["shapes"])

    def test_the_count_matches_the_marked_rows(self):
        found = digest.summarise_off_target(
            ["frontend", "frontend", "data", "backend"], targets={"backend"})
        self.assertEqual(found["count"], 3)

    def test_each_offending_shape_appears_once(self):
        found = digest.summarise_off_target(["frontend"] * 5, targets={"backend"})
        self.assertEqual(found["shapes"], ["frontend"])

    def test_nothing_off_target_reports_nothing(self):
        found = digest.summarise_off_target(["backend", "fullstack"],
                                            targets={"backend", "fullstack"})
        self.assertEqual(found["count"], 0)
        self.assertEqual(found["shapes"], [])

    def test_an_unknown_shape_is_not_counted_against_him(self):
        found = digest.summarise_off_target([None, "backend"], targets={"backend"})
        self.assertEqual(found["count"], 0)
