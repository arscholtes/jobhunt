"""Fit scoring.

Deliberately a transparent keyword model rather than an embedding or a language
model call: the score has to be arguable. Every point is traceable to a term in
the posting, so a bad ranking is a profile bug you can fix, not a black box.

Culture fit is not scored here — that needs research the posting cannot supply.
"""
import re

WEIGHTS = {"title": 30, "skills": 40, "interests": 15, "location": 15}


def _terms(text):
    return " " + re.sub(r"[^a-z0-9+#. -]+", " ", (text or "").lower()) + " "


def _hit(term, haystack):
    return re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", haystack)


def dealbreaker(job, profile):
    """Return the reason this posting is disqualified, or None."""
    hay = _terms(job["title"] + " " + (job.get("description") or ""))
    for d in profile.get("dealbreakers", []):
        if _hit(d["pattern"], hay):
            return f"{d['pattern']} ({d.get('why', 'excluded')})"
    title = _terms(job["title"])
    for bad in profile["search"]["exclude_titles"]:
        if _hit(bad, title):
            return f"excluded title: {bad}"
    return None


def score(job, profile):
    """Return (total 0-100, breakdown dict). Higher is a better fit."""
    title = _terms(job["title"])
    body = _terms(job["title"] + " " + (job.get("description") or ""))
    search = profile["search"]
    out = {}

    wanted = search["titles"]
    out["title"] = WEIGHTS["title"] if any(_hit(t, title) for t in wanted) else 0

    def weighted(table):
        got = {k: v for k, v in table.items() if _hit(k, body)}
        ceiling = sum(sorted(table.values(), reverse=True)[:6]) or 1
        return min(sum(got.values()) / ceiling, 1.0), sorted(got)

    if profile["skills"]:
        frac, matched = weighted(profile["skills"])
        out["skills"] = round(WEIGHTS["skills"] * frac, 1)
        out["skills_matched"] = matched
    else:
        out["skills"] = 0

    if profile["interests"]:
        frac, matched = weighted(profile["interests"])
        out["interests"] = round(WEIGHTS["interests"] * frac, 1)
        out["interests_matched"] = matched
    else:
        out["interests"] = 0

    loc = _terms(job.get("location") or "")
    if job.get("remote"):
        out["location"] = WEIGHTS["location"]
    elif any(_hit(l, loc) for l in search["locations"]):
        out["location"] = WEIGHTS["location"]
    elif search["remote_only"]:
        out["location"] = 0
    else:
        out["location"] = WEIGHTS["location"] * 0.3

    total = round(sum(v for k, v in out.items() if isinstance(v, (int, float))), 1)
    return min(total, 100.0), out
