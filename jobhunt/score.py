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


def _hit_prefix(term, haystack):
    """Like _hit but allows a suffix: 'intern' catches 'internship'.

    Only used for title exclusions, where 'intern' should disqualify
    'Software Engineer Internship' — a strict boundary match let those through.
    """
    return re.search(r"(?<![a-z0-9])" + re.escape(term.lower()), haystack)


def strip_boilerplate(description, boilerplate, suffix=""):
    """Remove a company's repeated preamble from one posting's description.

    Text identical across every posting a company makes is marketing, not role
    content — but every technology it names is read as a skill the role wants. A
    company that lists its whole stack on all 219 of its postings hands each of
    them a perfect skills score, which ranks its field roles above its engineering
    ones. Stripping the shared prefix is what makes the remaining score about the
    role.

    @param description [String, nil] the posting body
    Both ends are stripped. Across the stored corpus the shared tail is usually
    the larger half — benefits, EEO statements and stack blurbs sit at the end —
    so removing only the preamble leaves most of the distortion behind.

    @param boilerplate [String, nil] the company's shared prefix, from culture.boilerplate
    @param suffix [String, nil] the shared tail, from culture.boilerplate_suffix
    @return [String] the role-specific remainder
    """
    text = description or ""
    start = len(boilerplate) if boilerplate and text.startswith(boilerplate) else 0
    end = len(text) - len(suffix) if suffix and text.endswith(suffix) else len(text)
    # A posting that is nothing but boilerplate would otherwise strip past itself.
    return text[start:end] if start < end else ""


def dealbreaker(job, profile):
    """Return the reason this posting is disqualified, or None."""
    hay = _terms(job["title"] + " " + (job.get("description") or ""))
    for d in profile.get("dealbreakers", []):
        if _hit(d["pattern"], hay):
            return f"{d['pattern']} ({d.get('why', 'excluded')})"
    title = _terms(job["title"])
    for bad in profile["search"]["exclude_titles"]:
        if _hit_prefix(bad, title):
            return f"excluded title: {bad}"
    return None


def score(job, profile, boilerplate="", suffix=""):
    """Return (total, breakdown dict). Higher is a better fit.

    @param boilerplate [String] the company's shared description prefix
    @param suffix [String] the company's shared description tail — usually the
      larger half; both are stripped before terms are read so a role is scored
      on its own content

    The base components sum to 100 by construction, but the total is deliberately
    not capped there: interview and comp signals are added on top, and a posting
    that is both a perfect content match and a good process match should be able
    to say so rather than tie with every other perfect match at the ceiling.

    The floor stays at 0 because -1 is the disqualified sentinel.
    """
    title = _terms(job["title"])
    # The title is always role-specific, so it is never stripped — only the body is.
    body = _terms(job["title"] + " " + strip_boilerplate(job.get("description"), boilerplate, suffix))
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
        # Elsewhere-onsite is a preference, never a filter: relocation is a
        # tradeoff against comp, not a hard no. Tune with search.elsewhere_weight.
        out["location"] = round(WEIGHTS["location"] * search.get("elsewhere_weight", 0.3), 1)

    total = round(sum(v for k, v in out.items() if isinstance(v, (int, float))), 1)
    return max(total, 0.0), out
