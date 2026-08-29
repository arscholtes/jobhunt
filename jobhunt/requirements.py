"""What the highest-scoring postings actually ask for.

Three questions, answered against the live shortlist rather than a snapshot:
which profile skills the best matches keep demanding, which are being weighted
for and never asked about, and which terms keep appearing that the profile has no
opinion on at all. The third is the one worth acting on — it is the gap between
what the market wants and what the profile knows to look for.

Terms are counted per POSTING, not per occurrence: a company that names Kubernetes
nine times in one advert wants it once. Boilerplate comes off first for the same
reason it does in scoring — a stack blurb repeated on every advert is marketing,
and counting it would report the company's marketing as market demand.
"""

from __future__ import annotations

import re
from collections import Counter

from .score import _hit, _terms, strip_boilerplate

# The unmet list is deliberately a frequency count with a stoplist, not a term
# extractor. A stoplist that had to enumerate English would never be finished, and
# the consumer is a person reading a digest — a little noise costs them a skim,
# whereas an aggressive filter would quietly drop the real signal.
#
# A term has to appear in this share of the shortlist before it is a signal
# rather than one company's preference.
UNMET_THRESHOLD = 0.25
UNMET_LIMIT = 20
MIN_TERM_LEN = 3

# Ordinary prose that survives tokenising. Not a general stopword list — only what
# actually shows up at the top of a job-advert frequency count.
STOP = {
    "the", "and", "with", "you", "will", "work", "team", "for", "our", "are", "that", "this",
    "have", "from", "your", "not", "all", "can", "who", "was", "has", "but", "his", "her",
    "they", "them", "their", "its", "than", "then", "there", "here", "what", "when", "where",
    "how", "why", "which", "into", "out", "about", "over", "more", "most", "some", "any",
    "other", "such", "only", "own", "same", "very", "just", "also", "each", "both", "well",
    "role", "roles", "job", "jobs", "position", "company", "companies", "product", "products",
    "engineer", "engineers", "engineering", "software", "developer", "development", "developers",
    "experience", "experiences", "years", "year", "skills", "skill", "ability", "strong",
    "working", "build", "building", "help", "helping", "including", "include", "includes",
    "across", "within", "using", "use", "used", "new", "high", "great", "good", "best",
    "customers", "customer", "users", "user", "business", "technical", "technology", "systems",
    "system", "data", "code", "time", "make", "making", "support", "supporting",
    "opportunity", "opportunities", "benefits", "compensation", "salary", "equity", "range",
    "employment", "employer", "applicants", "candidates", "candidate", "apply", "application",
    "please", "requirements", "required", "qualifications", "preferred", "responsibilities",
    "world", "people", "teams", "may", "one", "two", "three", "per", "day", "days", "week",
    "you'll", "we're", "we", "us", "it", "is", "as", "at", "be", "by", "in", "of", "on", "or",
    "to", "an", "a", "if", "do", "does", "so", "up", "we'll", "our", "his",
    # Advert verbs and nouns that read as requirements but name nothing learnable.
    "design", "designing", "features", "feature", "improve", "improving", "core", "tools",
    "tooling", "scale", "scaling", "collaborate", "collaboration", "ship", "shipping",
    "production", "directly", "workflows", "workflow", "partner", "partners", "drive",
    "driving", "own", "owning", "deliver", "delivering", "impact", "growth", "quality",
    "solutions", "solution", "platform", "platforms", "services", "service", "process",
    "processes", "projects", "project", "problems", "problem", "complex", "senior", "staff",
    "lead", "leading", "manage", "managing", "cross-functional", "stakeholders", "reliability",
    "performance", "architecture", "infrastructure", "internal", "external", "global",
    "review", "built", "bring", "contribute", "familiarity", "closely", "reliable", "power",
    "location", "remote", "frameworks", "framework", "https", "http", "www", "com",
}
TOKEN = re.compile(r"[a-z][a-z0-9+#.-]{2,}")


def _bodies(rows, boilerplate=None):
    """@return [Array<String>] normalised, boilerplate-free text, one per posting."""
    boilerplate = boilerplate or {}
    out = []
    for r in rows:
        pre, suf = boilerplate.get(r["company"], ("", "")) if r["company"] in boilerplate else ("", "")
        body = strip_boilerplate(r.get("description") if hasattr(r, "get") else r["description"], pre, suf)
        out.append(_terms((r["title"] or "") + " " + body))
    return out


def _is_known(token, known):
    """Whether the profile already has an opinion on this token.

    Matches a naive plural in both directions, so "apis" is not reported as a gap
    in a profile that weights "api". Naive is the right depth here: a stemmer
    would be a dependency, and the README promises none.

    @param token [String] a token from a posting
    @param known [Set<String>] profile skills and interests, lowercased
    @return [Boolean]
    """
    variants = {token, token.rstrip("s"), token + "s"}
    for k in known:
        if k in variants or k.rstrip("s") in variants:
            return True
        if _hit(k, " " + token + " "):
            return True
    return False


def summarise(rows, profile, boilerplate=None):
    """Read the shortlist and report what it asks for.

    @param rows [Array<Hash>] the top-scoring postings
    @param profile [Hash] loaded profile.toml
    @param boilerplate [Hash] company -> (prefix, suffix) to strip first
    @return [Hash] {postings, demanded, unasked, unmet}
    """
    bodies = _bodies(rows, boilerplate)
    n = len(bodies)
    skills = profile.get("skills", {})

    demanded, unasked = [], []
    for term, weight in skills.items():
        count = sum(1 for b in bodies if _hit(term, b))
        entry = {"term": term, "weight": weight, "count": count,
                 "share": (count / n) if n else 0.0}
        (demanded if count else unasked).append(entry)
    demanded.sort(key=lambda d: (-d["count"], d["term"]))
    unasked.sort(key=lambda d: (-d["weight"], d["term"]))

    known = {t.lower() for t in skills} | {t.lower() for t in profile.get("interests", {})}
    seen = Counter()
    for b in bodies:
        tokens = {t.strip(".-") for t in TOKEN.findall(b)}
        for token in {t for t in tokens if len(t) >= MIN_TERM_LEN and t not in STOP}:
            if not _is_known(token, known):
                seen[token] += 1

    floor = max(2, int(n * UNMET_THRESHOLD)) if n else 0
    unmet = [{"term": t, "count": c, "share": c / n}
             for t, c in seen.most_common() if c >= floor][:UNMET_LIMIT]

    return {"postings": n, "demanded": demanded, "unasked": unasked, "unmet": unmet}


def render(summary):
    """@return [String] the digest as plain text."""
    n = summary["postings"]
    if not n:
        return "No scored postings above the floor — nothing to read the market from."

    out = [f"What the top {n} postings ask for", ""]
    out.append("  ASKED FOR — profile skills the shortlist keeps naming")
    for d in summary["demanded"][:15]:
        bar = "█" * round(10 * d["share"]) + "·" * (10 - round(10 * d["share"]))
        out.append(f"    {d['term']:<22} {bar}  {d['count']:>3}/{n}  (weight {d['weight']})")

    if summary["unasked"]:
        out += ["", "  NEVER ASKED — weighted for, and absent from every posting"]
        for d in summary["unasked"][:10]:
            out.append(f"    {d['term']:<22} weight {d['weight']} — consider moving it")

    if summary["unmet"]:
        out += ["", "  UNCLAIMED — frequent terms the profile has no opinion on.",
                "  Raw frequency, not a curated list: skim it. Advert prose leaks through,",
                "  because filtering it perfectly would mean enumerating English."]
        for u in summary["unmet"]:
            out.append(f"    {u['term']:<22} {u['count']:>3}/{n}  ({u['share']:.0%})")
    out.append("")
    return "\n".join(out)
