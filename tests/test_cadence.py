"""Shipping cadence: the one culture term the postings corpus cannot see.

'Ships often' carries the highest weight in the profile and reads 'unknown' for
every company, because a job posting never says how often the company ships. The
answer lives in commit history and changelogs, so it is fetched — and every fetch
is injected, so neither the tests nor CI ever touch the network.
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import cadence


def days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def repos(*ages):
    return [{"name": f"r{i}", "pushed_at": days_ago(a), "fork": False, "archived": False}
            for i, a in enumerate(ages)]


class OrgResolutionTests(unittest.TestCase):
    def test_a_company_name_is_its_own_org_by_default(self):
        self.assertEqual(cadence.github_org_for("gitlab", {}), "gitlab")

    def test_a_name_is_lowercased_and_despaced(self):
        self.assertEqual(cadence.github_org_for("Fly IO", {}), "fly-io")

    def test_an_override_wins(self):
        self.assertEqual(cadence.github_org_for("replit", {"replit": "replit-labs"}), "replit-labs")

    def test_an_override_of_none_means_the_company_has_no_org(self):
        self.assertIsNone(cadence.github_org_for("someco", {"someco": None}))


class GithubCadenceTests(unittest.TestCase):
    def fetcher(self, payload):
        self.calls = []

        def fetch(url, timeout=20):
            self.calls.append(url)
            return payload
        return fetch

    def test_many_recently_pushed_repos_read_as_shipping_often(self):
        c = cadence.github_cadence("acme", fetch=self.fetcher(repos(*([1] * 12))))
        self.assertEqual(c["active_30d"], 12)

    def test_stale_repos_do_not_count_as_recent(self):
        c = cadence.github_cadence("acme", fetch=self.fetcher(repos(400, 500, 600)))
        self.assertEqual(c["active_30d"], 0)

    def test_forks_are_not_evidence_of_shipping(self):
        payload = repos(1, 1)
        payload[0]["fork"] = True
        c = cadence.github_cadence("acme", fetch=self.fetcher(payload))
        self.assertEqual(c["active_30d"], 1)

    def test_archived_repos_are_not_evidence_of_shipping(self):
        payload = repos(1, 1)
        payload[0]["archived"] = True
        c = cadence.github_cadence("acme", fetch=self.fetcher(payload))
        self.assertEqual(c["active_30d"], 1)

    def test_an_org_with_no_repos_is_a_real_answer_not_an_error(self):
        c = cadence.github_cadence("acme", fetch=self.fetcher([]))
        self.assertEqual(c["active_30d"], 0)
        self.assertEqual(c["repos"], 0)

    def test_a_fetch_failure_yields_no_answer_rather_than_a_zero(self):
        def boom(url, timeout=20):
            raise cadence.FetchError("nope")
        # An unreachable API is "unknown", never "this company never ships".
        self.assertIsNone(cadence.github_cadence("acme", fetch=boom))

    def test_the_request_is_unauthenticated_and_sorted_by_push(self):
        f = self.fetcher(repos(1))
        cadence.github_cadence("acme", fetch=f)
        self.assertIn("orgs/acme/repos", self.calls[0])
        self.assertIn("sort=pushed", self.calls[0])

    def test_a_malformed_repo_entry_is_skipped_not_fatal(self):
        payload = repos(1) + [{"name": "bad"}]
        c = cadence.github_cadence("acme", fetch=self.fetcher(payload))
        self.assertEqual(c["active_30d"], 1)


class FeedCadenceTests(unittest.TestCase):
    ATOM = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><updated>{a}</updated></entry>'
            '<entry><updated>{b}</updated></entry></feed>')
    RSS = ('<?xml version="1.0"?><rss><channel>'
           '<item><pubDate>Mon, 01 Jan 2029 00:00:00 GMT</pubDate></item>'
           '</channel></rss>')

    def test_recent_atom_entries_are_counted(self):
        xml = self.ATOM.format(a=days_ago(3), b=days_ago(10))
        c = cadence.feed_cadence("http://x/feed", fetch_text=lambda u, timeout=20: xml)
        self.assertEqual(c["entries_90d"], 2)

    def test_old_atom_entries_are_not_counted(self):
        xml = self.ATOM.format(a=days_ago(300), b=days_ago(400))
        c = cadence.feed_cadence("http://x/feed", fetch_text=lambda u, timeout=20: xml)
        self.assertEqual(c["entries_90d"], 0)

    def test_malformed_xml_yields_no_answer(self):
        self.assertIsNone(cadence.feed_cadence("http://x", fetch_text=lambda u, timeout=20: "<not"))

    def test_a_feed_failure_yields_no_answer(self):
        def boom(url, timeout=20):
            raise cadence.FetchError("nope")
        self.assertIsNone(cadence.feed_cadence("http://x", fetch_text=boom))


class FalseZeroTests(unittest.TestCase):
    """An absent answer must never be scored as a bad answer.

    gitlab hosts its code on gitlab.com, so its GitHub org returns zero usable
    repos. Read literally that is "0/0 pushed in 30d" and scores 0.0 — the tool
    confidently reporting that GitLab never ships. Too small a sample is unknown.
    """

    def test_an_org_with_no_usable_repos_is_unknown_not_zero(self):
        self.assertIsNone(cadence.ships_often_score({"active_30d": 0, "repos": 0, "org": "gitlab"}, None))

    def test_an_org_below_the_sample_floor_is_unknown(self):
        below = cadence.MIN_REPOS - 1
        self.assertIsNone(cadence.ships_often_score({"active_30d": 0, "repos": below, "org": "acme"}, None))

    def test_an_org_at_the_sample_floor_is_a_real_answer(self):
        at = cadence.MIN_REPOS
        self.assertIsNotNone(cadence.ships_often_score({"active_30d": 0, "repos": at, "org": "acme"}, None))

    def test_a_feed_still_answers_when_the_org_sample_is_too_small(self):
        frac, why = cadence.ships_often_score({"active_30d": 0, "repos": 0, "org": "gitlab"},
                                              {"entries_90d": 12, "url": "http://x"})
        self.assertGreater(frac, 0)
        self.assertNotIn("repos", why)


class ScoringTests(unittest.TestCase):
    def test_no_evidence_scores_nothing_rather_than_zero(self):
        self.assertIsNone(cadence.ships_often_score(None, None))

    def test_a_very_active_org_saturates(self):
        frac, why = cadence.ships_often_score({"active_30d": 40, "repos": 60, "org": "acme"}, None)
        self.assertEqual(frac, 1.0)
        self.assertIn("acme", why)

    def test_a_dormant_org_scores_zero_but_is_still_an_answer(self):
        frac, why = cadence.ships_often_score({"active_30d": 0, "repos": 20, "org": "acme"}, None)
        self.assertEqual(frac, 0.0)
        self.assertIsInstance(why, str)

    def test_a_blog_alone_can_answer_the_question(self):
        frac, why = cadence.ships_often_score(None, {"entries_90d": 6, "url": "http://x"})
        self.assertGreater(frac, 0)

    def test_the_stronger_of_the_two_signals_wins(self):
        weak = {"active_30d": 1, "repos": 30, "org": "acme"}
        strong = {"entries_90d": 12, "url": "http://x"}
        frac, _ = cadence.ships_often_score(weak, strong)
        only_weak, _ = cadence.ships_often_score(weak, None)
        self.assertGreater(frac, only_weak)

    def test_the_evidence_names_its_source_so_a_wrong_answer_is_arguable(self):
        _, why = cadence.ships_often_score({"active_30d": 5, "repos": 30, "org": "acme"}, None)
        self.assertIn("30d", why)


if __name__ == "__main__":
    unittest.main()
