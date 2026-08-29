"""Company-level culture evidence, derived from a company's whole board.

One posting is a sales document. A company's ENTIRE posting set is much harder to
pose in: if only two of nineteen roles are remote, "remote friendly" is not what
they are, whatever any single posting says.

So culture here is an aggregate over the corpus already in sqlite — no new
requests, no keys, no scraping. Every number traces to postings on disk, and a
term the corpus cannot speak to scores UNKNOWN rather than zero. Unknown is
excluded from the denominator, so silence never masquerades as a bad result.

Deliberately a separate axis from fit. Averaging "does this match what I do" with
"is this a room I would do well in" destroys both; they are different questions and
get answered side by side.
"""
import re

# Engineering-ish titles, used to size the org and to avoid judging a company's
# culture by its sales postings.
ENG = re.compile(r"engineer|developer|architect|sre|devops|programmer", re.I)

ONCALL = re.compile(r"on[- ]call|pager ?duty|pager rotation|24/7 rotation|incident rotation", re.I)
DOCS = re.compile(
    r"design doc|rfc\b|written communication|writes? (?:well|clearly)|documentation[- ]first"
    r"|async(?:hronous)? (?:communication|written|first)|write (?:things )?down|handbook"
    r"|strong writer|written proposal", re.I)
REMOTE_HOSTILE = re.compile(r"in[- ]office|onsite required|hybrid|days? (?:per|a) week in", re.I)


def _share(rows, pattern):
    """Fraction of postings whose text matches, and the matching count."""
    hits = sum(1 for r in rows if pattern.search((r["description"] or "") + " " + (r["title"] or "")))
    return (hits / len(rows) if rows else 0.0), hits


def boilerplate(rows, floor=200):
    """Longest common prefix across a company's descriptions.

    Text identical on every posting is marketing, not role content. Its length is
    both a culture tell and — more urgently — a scoring distortion, because every
    technology named in it is inherited by every role the company posts.
    """
    descs = _descriptions(rows)
    if not descs:
        return ""
    first, shortest = descs[0], min(len(d) for d in descs)
    i = 0
    while i < shortest and all(d[i] == first[i] for d in descs):
        i += 1
    if i == shortest:
        # Every posting identical: there is no role content to separate, and
        # claiming the whole body is boilerplate would leave nothing to score.
        return ""
    return first[:i] if i >= floor else ""


def _descriptions(rows):
    """@return [Array<String>] descriptions, or [] when there are too few to judge."""
    descs = [r["description"] or "" for r in rows if r["description"]]
    return descs if len(descs) >= 3 else []


def boilerplate_suffix(rows, floor=200):
    """Longest common suffix across a company's descriptions.

    Measured across the stored corpus this is usually the larger half: gitlab
    repeats 1,483 characters of preamble and 3,708 of tail, and asana repeats
    2,014 characters of tail with no shared preamble at all. Benefits, EEO
    statements and stack blurbs sit at the end, so a prefix-only stripper leaves
    most of the scoring distortion in place.

    @param rows [Array<Hash>] every posting stored for one company
    @param floor [Integer] shorter than this is coincidence, not boilerplate
    @return [String] the shared tail, or ""
    """
    descs = _descriptions(rows)
    if not descs:
        return ""
    first, shortest = descs[0], min(len(d) for d in descs)
    i = 0
    while i < shortest and all(d[-1 - i] == first[-1 - i] for d in descs):
        i += 1
    if i == shortest:
        return ""
    return first[len(first) - i:] if i >= floor else ""


# Each known culture term maps to a probe returning (score 0-1, evidence string),
# or None when the corpus genuinely cannot speak to it.
def _remote_friendly(rows):
    remote = sum(1 for r in rows if r["remote"])
    frac = remote / len(rows)
    return frac, f"{remote}/{len(rows)} postings remote ({frac:.0%})"


def _no_oncall(rows):
    frac, hits = _share(rows, ONCALL)
    return 1.0 - frac, f"on-call language in {hits}/{len(rows)} postings ({frac:.0%})"


def _writes_things_down(rows):
    frac, hits = _share(rows, DOCS)
    # Rare language even at companies that do write. Treat a third as saturation
    # rather than demanding every posting say it.
    return min(frac / 0.33, 1.0), f"writing/doc culture named in {hits}/{len(rows)} postings"


def _small_team(rows):
    eng = sum(1 for r in rows if ENG.search(r["title"] or ""))
    # Open eng reqs as an inverse size proxy: 3 open roles reads small, 40 does not.
    score = max(0.0, min(1.0, 1.0 - (eng - 3) / 37))
    return score, f"{eng} open engineering roles"


PROBES = {
    "remote friendly": _remote_friendly,
    "no on-call pager rotation": _no_oncall,
    "writes things down": _writes_things_down,
    "small engineering team": _small_team,
    # Cadence needs commit or blog history; the corpus cannot see it.
    "ships often": None,
}


def assess(rows, profile, ships_often=None):
    """Score one company's culture 0-100 against the profile's [culture] weights.

    Stays pure: "ships often" is the one term the corpus cannot answer, and its
    evidence is passed in rather than fetched here, so scoring never depends on
    the network being up.

    @param rows [list<sqlite3.Row>] every posting stored for that company
    @param profile [dict] loaded profile.toml
    @param ships_often [tuple(float, str), nil] external cadence evidence, from
      jobhunt.cadence.ships_often_score; nil leaves the term unknown
    @return [dict] score, coverage, per-term evidence, boilerplate length
    """
    weights = profile.get("culture", {})
    earned = possible = 0.0
    terms = []
    for term, weight in sorted(weights.items(), key=lambda kv: -kv[1]):
        probe = PROBES.get(term)
        if probe is None:
            supplied = ships_often if term == "ships often" else None
            if supplied is None:
                terms.append({"term": term, "weight": weight, "score": None,
                              "why": "unknown — needs commit history or a blog feed"})
                continue
            frac, why = supplied
        else:
            frac, why = probe(rows)
        earned += weight * frac
        possible += weight
        terms.append({"term": term, "weight": weight, "score": round(frac, 2), "why": why})

    bp = boilerplate(rows)
    return {
        "score": round(100 * earned / possible, 1) if possible else None,
        "covered": round(possible), "total_weight": round(sum(weights.values())),
        "postings": len(rows), "boilerplate_chars": len(bp), "terms": terms,
    }
