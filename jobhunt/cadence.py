"""How often a company actually ships.

'Ships often' carries the highest weight in the profile and reads "unknown" for
every company, because the postings cannot answer it: a job posting never says how
often anyone ships. The answer lives in commit history and changelogs, so this is
the one culture probe that leaves the postings.

Every fetch is injected. That keeps the network at the edges — tests and CI never
touch it — and it keeps a fetch failure distinguishable from a real zero. An
unreachable API means "unknown", never "this company never ships"; a scoring
model that cannot tell those apart will confidently punish a company for an
outage on someone else's server.

Nothing here is added to the fit total. Culture is a separate axis, shown beside
the score and never summed into it.
"""

from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .sources._http import UA, FetchError, get_json

# Sampling the most recently pushed repos answers "is this org alive" without
# paging an org with hundreds of them.
REPO_SAMPLE = 60
GITHUB_ORG_REPOS = "https://api.github.com/orgs/{org}/repos?sort=pushed&direction=desc&per_page={n}"
ACTIVE_WINDOW_DAYS = 30
FEED_WINDOW_DAYS = 90
# Ten repos touched in a month, or a post a fortnight, is already "ships often".
# Beyond that the number stops meaning more.
REPO_SATURATION = 10
# Below this many usable repos the org says nothing about shipping — the company
# may host elsewhere (gitlab does) or keep its work private. Scoring that as a
# zero would report "never ships" from an absence of evidence.
MIN_REPOS = 3
FEED_SATURATION = 6


def github_org_for(company, overrides=None):
    """The GitHub org for a company, or None when it is known not to have one.

    @param company [String] the company as the job board names it
    @param overrides [Hash] profile-supplied company -> org (or None) mapping
    @return [String, nil]
    """
    overrides = overrides or {}
    key = (company or "").strip().lower()
    if key in overrides:
        return overrides[key]
    return key.replace(" ", "-").replace("_", "-") or None


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:  # urllib raises a wide family; the caller only needs "no answer"
        raise FetchError(f"{url} unreachable: {e}") from e


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def github_cadence(org, fetch=get_json):
    """Recent push activity across an org's public repos.

    @param org [String] GitHub org slug
    @param fetch [Proc] injected JSON fetcher
    @return [Hash, nil] {org, repos, active_30d}, or nil when the API could not answer
    """
    if not org:
        return None
    try:
        payload = fetch(GITHUB_ORG_REPOS.format(org=org, n=REPO_SAMPLE), timeout=20)
    except FetchError:
        return None
    if not isinstance(payload, list):
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=ACTIVE_WINDOW_DAYS)
    counted = active = 0
    for repo in payload:
        if not isinstance(repo, dict) or repo.get("fork") or repo.get("archived"):
            continue
        counted += 1
        pushed = _parse_ts(repo.get("pushed_at"))
        if pushed and pushed > cutoff:
            active += 1
    return {"org": org, "repos": counted, "active_30d": active}


def feed_cadence(url, fetch_text=_fetch_text):
    """Post frequency from a blog, changelog or release feed (RSS or Atom).

    @param url [String] feed url
    @param fetch_text [Proc] injected text fetcher
    @return [Hash, nil] {url, entries_90d}, or nil when the feed could not be read
    """
    if not url:
        return None
    try:
        body = fetch_text(url, timeout=20)
    except FetchError:
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=FEED_WINDOW_DAYS)
    recent = 0
    for tag in ("{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published",
                "pubDate", "updated", "published"):
        for node in root.iter(tag):
            ts = _parse_ts(node.text) or _parse_rfc822(node.text)
            if ts and ts > cutoff:
                recent += 1
        if recent:
            break
    return {"url": url, "entries_90d": recent}


def _parse_rfc822(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def ships_often_score(github, feed):
    """Combine the available evidence into a 0-1 probe result.

    @param github [Hash, nil] github_cadence output
    @param feed [Hash, nil] feed_cadence output
    @return [Array(Float, String), nil] (score, evidence), or nil when nothing could answer
    """
    parts = []
    best = None

    if github is not None and github["repos"] >= MIN_REPOS:
        frac = min(github["active_30d"] / REPO_SATURATION, 1.0)
        parts.append(f"{github['active_30d']}/{github['repos']} {github['org']} repos "
                     f"pushed in {ACTIVE_WINDOW_DAYS}d")
        best = frac
    if feed is not None:
        frac = min(feed["entries_90d"] / FEED_SATURATION, 1.0)
        parts.append(f"{feed['entries_90d']} feed entries in {FEED_WINDOW_DAYS}d")
        best = frac if best is None else max(best, frac)

    if best is None:
        return None
    return round(best, 2), "; ".join(parts)


def for_company(company, org_overrides=None, feeds=None,
                fetch=get_json, fetch_text=_fetch_text):
    """Resolve shipping cadence for one company from every source available.

    @param company [String] as the job board names it
    @param org_overrides [Hash] company -> github org (or None for "has none")
    @param feeds [Hash] company -> blog/changelog feed url
    @return [Hash] {github, feed, score, why} — score/why are nil when nothing answered
    """
    org = github_org_for(company, org_overrides)
    gh = github_cadence(org, fetch=fetch) if org else None
    feed = feed_cadence((feeds or {}).get((company or "").lower()), fetch_text=fetch_text)
    scored = ships_often_score(gh, feed)
    return {"github": gh, "feed": feed,
            "score": scored[0] if scored else None,
            "why": scored[1] if scored else None}
