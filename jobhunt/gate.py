"""Which resume a posting should get, and why.

Two independent axes, because one does not determine the other: a Senior
Software Engineer at an LLM-infrastructure company and one at a logistics SaaS
share a title and want different evidence on page one.

  role shape  — what the job is        (from the title, body as fallback)
  domain      — what the company builds (from the body)

Deliberately a precedence table rather than a model, for the same reason the
scorer is a keyword model: the choice has to be arguable. Every decision carries
the rule that produced it, so a wrong pick is a line to edit here rather than a
verdict to accept.

Eligibility appears as *flags*, never as a silent filter. A region lock or a
degree clause changes how a posting is framed and whether it is worth the
effort; it is not this module's business to hide it.
"""
import re

from . import location as location_mod

# Ordered. First match wins, so the specific shapes are listed before the
# catch-all "software engineer", which would otherwise swallow all of them.
SHAPES = [
    ("fde", r"forward[- ]deployed|solutions engineer|support engineer|field engineer"
            r"|technical solutions|professional services|implementation engineer"),
    ("frontend", r"front[- ]?end|\bui engineer|design engineer|web developer"),
    ("backend", r"back[- ]?end|server[- ]side"),
    ("fullstack", r"full[- ]?stack"),
    ("platform", r"\bplatform\b|developer experience|\bdevex\b|\bdx\b|infrastructure"
                 r"|\bsre\b|site reliability|devops|internal tools"),
    ("product", r"product engineer"),
    ("data", r"data engineer|analytics engineer|\bml engineer|machine learning"
             r"|\bai engineer|data scientist"),
    ("security", r"\bsecurity\b|\bappsec\b|\binfosec\b"),
    ("mobile", r"\bios\b|\bandroid\b|\bmobile\b"),
    ("generic", r"software (engineer|developer)|engineer"),
]

# Shapes with no resume of their own fall back to the nearest one that has.
FALLBACK = {"frontend": "fullstack", "product": "fullstack",
            "data": "backend", "security": "backend", "mobile": "fullstack"}

# Ordered by how strongly the domain should steer the resume when a posting
# matches more than one. AI outranks Rails: the stack is visible in the skills
# section either way, but the domain framing only gets said once, in the summary.
DOMAINS = [
    ("ai", r"\bllm\b|large language model|\bgenai\b|generative ai|foundation model"
           r"|\brag\b|agentic|ai agent|prompt engineering"),
    ("devtools", r"developer tool|developer experience|\bsdk\b|api platform"
                 r"|open source|ci/cd|developer productivity"),
    ("rails", r"ruby on rails|\brails\b|\bruby\b"),
]

REGION_LOCK = (
    r"\[(canada|uk|emea|apac|latam|india|germany|france|brazil|poland|australia)\]"
    r"|\b(emea|apac|latam|canada|uk|eu)[- ]only\b"
    r"|must (be|reside) (located )?in (canada|the uk|emea|europe|australia)"
    r"|eligible to work in (canada|the uk|australia|the eu)"
)
# Levels only count when the word is doing level work. Matching the bare terms
# put "engineering at Privy is distinguished by" and "manage and architect
# multi-tenant infrastructure" in the same bucket as a real staff posting — 19 of
# 34 matches were the ordinary English words, so the term must sit next to a role
# noun or an explicit level phrase to count.
LEVEL_ABOVE = (r"\b(staff|principal|distinguished)[- ]?(level)?[- ]?"
               r"(software |backend |platform |infrastructure |full[- ]?stack |product )?"
               r"engineer\b"
               r"|\bat the (staff|principal) level\b"
               r"|\bthis is a (staff|principal)[- ]level\b")
# Level terms are unambiguous in a title and ambiguous everywhere else: a title
# reading "Software Engineer, New Grad" IS the level, while the same words in a
# body are usually "unlike a new grad, you will..." or a link to a separate
# programme. So the title is matched loosely and the body only on an explicit
# statement about this role. Matching the body loosely flagged postings that
# merely mention mentoring juniors; matching the title strictly missed a New Grad
# posting scoring 92.
LEVEL_BELOW_TITLE = r"\b(new grad(uate)?|entry[- ]level|early career|university (grad|hire)|intern(ship)?|junior)\b"
LEVEL_BELOW_BODY = (r"\bthis (is|role is) an? (entry|junior)[- ]level\b"
                    r"|\b(intern|internship) (program|position)\b"
                    r"|\b0[- ]2 years\b")
DEGREE_HARD = (r"\b(bachelor|master)('?s)?( degree)?[^.]{0,40}\b(is )?required\b"
               r"|\brequire[sd]?\b[^.]{0,30}\b(bachelor|master)('?s)?( degree)?\b"
               r"|\bmust (have|possess)[^.]{0,30}\b(bachelor|master)('?s)?( degree)?\b")
# A degree named only to be waived is the opposite of a gate. "MS is helpful but
# not required" was matching DEGREE_HARD before this.
DEGREE_SOFT = (r"\b(degree|bachelor|master)[^.]{0,60}\b(not required|preferred|helpful|nice to have|a plus)\b"
               r"|\b(preferred|nice to have|a plus)[^.]{0,30}\b(degree|bachelor|master)")
DEGREE_EQUIV = r"or equivalent (practical )?experience|equivalent work experience|or equivalent training"


def _hay(text):
    """Lowercase plain text. Postings arrive as HTML, and the entity debris
    matters: an unstripped '&nbsp;' leaves the literal 'bsp', which matched the
    degree pattern as a stray 'bs'."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
    return re.sub(r"[^a-z0-9+#/\[\]. -]+", " ", text.lower())


def _first(table, hay):
    for name, pattern in table:
        m = re.search(pattern, hay)
        if m:
            return name, m.group(0).strip()
    return None, None


# A title has to name an engineering job before its body is worth reading for
# role shape. Without this, "Operations Associate, New Grad" classified as
# platform because the word "infrastructure" appeared somewhere in its body.
ENGINEERING_TITLE = r"engineer|developer|programmer|\bsre\b|architect|technologist"


def classify(job):
    """Return (shape, domain, reasons). Shape falls back to the title-neutral
    'generic' when nothing matches, never to None."""
    title, body = _hay(job.get("title")), _hay(job.get("description"))
    reasons = []

    # The catch-all entry is not a real match. A title reading "Senior Software
    # Engineer, <team>" names an engineering job and nothing more, so matching it
    # against 'generic' and stopping there skipped the body fallback that exists
    # for exactly this case — a third of top postings got the least-tailored
    # resume while their bodies said plainly what the role was.
    shape, hit = _first([s for s in SHAPES if s[0] != "generic"], title)
    if shape:
        reasons.append(f"shape={shape} from title term {hit!r}")
    elif re.search(ENGINEERING_TITLE, title):
        shape, hit = _first([s for s in SHAPES if s[0] != "generic"], body)
        if shape:
            reasons.append(f"shape={shape} from body term {hit!r} (title was ambiguous)")
        else:
            shape = "generic"
            reasons.append("shape=generic (engineering title, no specific shape)")
    else:
        shape = "generic"
        reasons.append(f"shape=generic (title {job.get('title')!r} does not name an "
                       f"engineering role — body not used)")

    # The fallback chooses a RESUME. It must not also decide what kind of role
    # this is: overwriting the shape here made a frontend posting report itself as
    # fullstack, and nothing downstream could tell that six of twenty selected
    # roles were frontend, ML or IT.
    role_shape = shape
    if shape in FALLBACK:
        reasons.append(f"shape {shape} has no resume of its own -> {FALLBACK[shape]}")
        shape = FALLBACK[shape]

    domain, hit = _first(DOMAINS, body)
    if domain:
        reasons.append(f"domain={domain} from body term {hit!r}")
    else:
        domain = "general"
        reasons.append("domain=general (no domain signal)")

    return shape, domain, reasons, role_shape


def flags(job):
    """Eligibility signals worth reading before applying. Displayed, never applied.

    Each is a (name, evidence) pair quoting the text that triggered it, so a
    false positive is visible as a false positive rather than a silent drop.
    """
    body = _hay(job.get("title") + " " + (job.get("description") or ""))
    out = []
    for name, pattern in (("region_locked", REGION_LOCK),
                          ("level_above", LEVEL_ABOVE),
                          ("degree_hard", DEGREE_HARD)):
        m = re.search(pattern, body)
        if m:
            out.append((name, m.group(0).strip()))

    # The location field says this outright; REGION_LOCK only reads title tags
    # and body phrasing, and missed every Dublin and São Paulo posting.
    where = location_mod.classify(job.get("location"))
    if where == "international":
        out.append(("international", location_mod.country(job.get("location")) or "outside the US"))

    m = re.search(LEVEL_BELOW_TITLE, _hay(job.get("title"))) or re.search(LEVEL_BELOW_BODY, body)
    if m:
        out.append(("level_below", m.group(0).strip()))
    for pattern, name in ((DEGREE_EQUIV, "equivalency_ok"), (DEGREE_SOFT, "degree_soft")):
        m = re.search(pattern, body)
        if m:
            out.append((name, m.group(0).strip()))
    # A degree that is waived, or satisfied by experience, is not a hard gate.
    if any(n in ("equivalency_ok", "degree_soft") for n, _ in out):
        out = [f for f in out if f[0] != "degree_hard"]
    return out


# Short forms for the shortlist and the digest, where the evidence string is too
# long to fit. The full evidence stays available through `jobhunt gate <id>`.
FLAG_LABELS = {
    "region_locked": "region-locked",
    "level_above": "above level",
    "level_below": "below level",
    "degree_hard": "degree required",
    "degree_soft": "degree preferred",
    "equivalency_ok": "experience accepted",
    "international": "international",
}


def flag_labels(job):
    """One short line naming this posting's eligibility flags, for a list row.

    A flag nobody sees is a silent filter wearing a different name, so these ride
    along with every listing rather than living only behind a subcommand.

    @param job [Hash] a posting
    @return [String] e.g. "region-locked · above level", or "" when clean
    """
    parts = []
    for name, why in flags(job):
        label = FLAG_LABELS.get(name, name)
        # The country matters more than the category: whether to chase a visa is
        # a different question per country.
        parts.append(f"{label} ({why})" if name == "international" else label)
    return " · ".join(parts)


def decide(job):
    """Full gate decision for one posting."""
    shape, domain, reasons, role_shape = classify(job)
    return {
        "variant": f"{shape}.{domain}",
        "shape": shape,
        # What the posting actually is, before the resume fallback flattened it.
        "role_shape": role_shape,
        "domain": domain,
        "reasons": reasons,
        "flags": flags(job),
    }
