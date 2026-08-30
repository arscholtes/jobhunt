"""Tailoring the material to one posting, and the brief written from it.

A market-frequency model lived here and has been removed rather than left
dormant. It decided what a requirement asked for from how rare its terms were,
which inverts on a tech corpus where the common terms are the important ones.
Dead code with passing tests beside it is worse than either alone, because it
reads as a supported path.

gate.py picks one of twenty pre-built shape.domain variants. That is variant
SELECTION, and it answers "which of my twenty resumes is closest". Tailoring
answers a different question — which of MY bullets speak to THIS posting's
language — and until now nothing asked it.

THE BRIEF IS NOT A COVER LETTER, deliberately. Generated prose carries a voice
that is not the applicant's, readers detect it, and the cost of being detected is
real. This produces a page to write FROM: the variant and the term that chose it,
what the posting asks for, the evidence for each ask, and the gaps.

THE GAPS ARE THE POINT. Everything else here is convenience — it saves re-reading
a posting and hand-picking bullets. Knowing what he does NOT match is the input
to the only decision that matters: whether to apply at all, and what to address
if he does.

There is no send path in this module and there should never be one. The README
promises an employer is never contacted, and a capability behind a flag that
defaults off is a capability that gets turned on at eleven at night by someone in
a hurry.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

# Applicant-tracking systems, by how much of a person's evening they cost.
FRICTION = {
    "low": ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com"),
    "high": ("myworkdayjobs.com", "taleo.net", "icims.com", "successfactors.com", "brassring.com"),
}
BULLETS_PER_ROLE = 5
# A line in a requirements list, however the posting punctuates it.
# A short list item is still a requirement. "Ruby" is four characters and is the
# whole ask; dropping it because it is brief manufactures a false gap.
BULLET_LINE = re.compile(r"^\s*(?:[-•*•]|\d+[.)])\s+(.{3,300})$", re.M)
# Below this length a shared prefix is coincidence rather than the same word.
STEM_MIN = 4
# A morphological variant differs by an ending, not by a whole word.
MAX_STEM_GAP = 3
# Below two characters a "name" is an initial or punctuation.
MIN_NAME_CHARS = 2
# Measured against the corpus rather than guessed. "What you bring" appears
# without the apostrophe-ll that the first version demanded, and Anthropic phrases
# it as "you may be a good fit if".
#
# "Bonus points" and "nice to have" are deliberately NOT requirements. A missing
# nice-to-have never decides whether to apply, and putting it in the gap list
# dilutes the one section that is a decision input rather than a convenience.
REQUIREMENT_HEADING = re.compile(
    r"(requirement|qualification|what you.{0,5}(need|bring|have)|who you are|"
    r"about you|we.{0,5}re looking for|must have|you have|good fit if|"
    r"skills? (and|&) experience|what we.{0,5}re looking for)", re.I)
STOP = {
    "the", "and", "with", "you", "will", "for", "our", "are", "that", "this", "have",
    "from", "your", "not", "all", "can", "who", "was", "but", "they", "them", "their",
    "its", "than", "then", "there", "here", "what", "when", "where", "how", "why",
    "which", "into", "out", "about", "over", "more", "most", "some", "any", "other",
    "such", "only", "own", "same", "very", "just", "also", "each", "both", "well",
    "work", "worked", "working", "team", "teams", "product", "products", "company",
    "experience", "years", "year", "strong", "build", "building", "built", "help",
    "including", "across", "within", "using", "use", "used", "new", "high", "great",
    "good", "best", "role", "job", "position", "engineer", "engineering", "software",
    "developer", "development", "senior", "staff", "lead", "plus", "nice", "must",
    "should", "would", "could", "ability", "skills", "deep", "solid", "proven",
}
TOKEN = re.compile(r"[a-z][a-z0-9+#.-]{1,}")


def _terms(text):
    """@return [set<str>] meaningful lowercase tokens, stripped of ordinary prose."""
    return {t.strip(".-") for t in TOKEN.findall((text or "").lower())
            if t not in STOP and len(t) > MIN_TOKEN_CHARS} - STOP


def _posting_terms(job):
    return _terms(f"{job.get('title') or ''} {job.get('description') or ''}")


def relevance(item, job):
    """How much of this posting's own vocabulary a bullet actually shares.

    @param item [Hash] a bullet or project with a `text`
    @param job [Hash] the posting
    @return [Integer] count of shared meaningful terms
    """
    return len(_terms(item.get("text")) & _posting_terms(job))


def _eligible(item, shape, domain):
    shapes, domains = item.get("shapes") or [], item.get("domains") or []
    return (not shapes or shape in shapes) and (not domains or domain in domains)


def select(items, job, shape=None, domain=None, limit=BULLETS_PER_ROLE):
    """Choose the bullets this posting should see, in the order they were written.

    Weight comes first and relevance is the tiebreaker, not the other way round.
    An earlier version of the sibling ranker added a flat relevance bonus, and
    three tagged weight-8 bullets pushed out an untagged weight-10 one — the
    posting's vocabulary overruling the author's judgment of his own best
    material. The posting refines the order; it does not get to overrule him.

    Survivors are restored to authoring order, because rank decides WHO survives
    and the author decides the sequence a reader meets them in.

    @return [Array<Hash>]
    """
    keep = [(n, i) for n, i in enumerate(items) if _eligible(i, shape, domain)]
    keep.sort(key=lambda pair: (pair[1].get("weight", 5),
                                relevance(pair[1], job),
                                shape in (pair[1].get("shapes") or []),
                                domain in (pair[1].get("domains") or [])),
              reverse=True)
    if limit:
        keep = keep[:limit]
    keep.sort(key=lambda pair: pair[0])
    return [i for _, i in keep]


# Boards serve HTML, not markdown. The first version of this looked for "- "
# lines and found requirements in 0 of 192 postings — a parser written against a
# format the data does not use, whose empty output reads exactly like "you match
# every requirement".
# A heading is not always a heading tag. Measured on the live corpus, 744 postings
# introduce their requirements with <p><strong>Requirements</strong></p> and only
# 249 use a real <h> tag — so matching h1-h6 alone left the gap analysis blank on
# three quarters of the shortlist, and blank while claiming the posting stated
# nothing. A bold or strong paragraph carrying only its own text is a heading in
# every way that matters here.
HTML_HEADING = re.compile(
    r"<h[1-6][^>]*>(.*?)</h[1-6]>"
    r"|<p[^>]*>\s*<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>\s*</p>",
    re.I | re.S)
HTML_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
# Lists that are not asks. Reporting these as gaps produces "no evidence of
# dental", which teaches the reader to distrust the section that matters most.
NOT_REQUIREMENTS = re.compile(
    r"(benefit|perk|compensation|salary|equal opportunity|about (us|the team|stripe)|"
    r"what we offer|our values|why join|responsibilit)", re.I)


def _strip(fragment):
    return " ".join(html.unescape(TAG.sub(" ", fragment or "")).split())


def _html_requirements(text):
    """Requirement list items, taken from the section their heading introduces."""
    out, seen = [], set()
    headings = list(HTML_HEADING.finditer(text))
    for i, h in enumerate(headings):
        label = _strip(h.group(1) or h.group(2) or "")
        if not REQUIREMENT_HEADING.search(label) or NOT_REQUIREMENTS.search(label):
            continue
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        for li in HTML_LI.findall(text[h.end():end]):
            item = _strip(li)
            key = item.lower()
            if MIN_REQUIREMENT_CHARS <= len(item) <= MAX_REQUIREMENT_CHARS and key not in seen:
                seen.add(key)
                out.append(item)
    return out


BULLET_BUDGET = 8
# Two characters or fewer is a preposition, not a skill.
MIN_TOKEN_CHARS = 2
MIN_OPTIONS = 2
MIN_REQUIREMENT_CHARS = 3
MAX_REQUIREMENT_CHARS = 300
MIN_WITHHELD = 2
EVIDENCE_PER_REQUIREMENT = 3
TOP_BULLETS_SCORED = 3


def bullets_for(roles, job, shape=None, domain=None, budget=BULLET_BUDGET):
    """Spend a fixed bullet budget on the roles this posting actually cares about.

    Without a budget the brief reprints the whole resume — twenty bullets across
    five roles on the first real run, including an esports division-manager role
    for a reinforcement-learning job. A second copy of the resume removes no
    tedium, which is the only thing this is measured on.

    Roles are ordered by how much they speak to the posting, the budget is spent
    down that order, and then the surviving roles are restored to resume order so
    the page still reads as a career rather than a ranking.

    @return [Array<Tuple(String, String, Array<Hash>)>] company, title, bullets
    """
    scored = []
    for n, role in enumerate(roles):
        chosen = select(role.get("bullets", []), job, shape, domain, limit=None)
        if not chosen:
            continue
        # The best few, not the sum of all: summing rewards a role for having
        # more bullets, which put two esports roles above the engineering ones
        # for a reinforcement-learning posting. A role's claim on the page is how
        # well its strongest material speaks to this posting.
        weight = sum(sorted((relevance(b, job) for b in chosen), reverse=True)[:TOP_BULLETS_SCORED])
        scored.append((weight, n, role, chosen))

    scored.sort(key=lambda t: -t[0])
    out, spent = [], 0
    for weight, n, role, chosen in scored:
        if spent >= budget:
            break
        # A role with nothing this posting mentions is padding, unless nothing
        # matched at all — in which case the best material is better than none.
        if weight == 0 and out:
            continue
        room = min(len(chosen), budget - spent, BULLETS_PER_ROLE)
        keep = _top(chosen, job, room)
        if keep:
            out.append((n, role.get("company", "?"), role.get("title", "?"), keep))
            spent += len(keep)

    out.sort(key=lambda t: t[0])
    return [(c, t, b) for _, c, t, b in out]


def _top(bullets, job, room):
    """The `room` most relevant bullets, restored to authoring order."""
    ranked = sorted(enumerate(bullets),
                    key=lambda p: (p[1].get("weight", 5), relevance(p[1], job)),
                    reverse=True)[:room]
    ranked.sort(key=lambda p: p[0])
    return [b for _, b in ranked]


def withheld(roles, shape=None, domain=None):
    """Material this variant cannot show, and the tags that hid it.

    The variant gate is his design and correct: a backend bullet does not belong
    on a fullstack resume. But when it hides most of a role, the page quietly
    fills with whatever was tagged broadly instead — and on real data that put
    two esports roles above the engineering ones. Saying what was withheld turns
    a silent filter into something he can act on, by widening a tag or by
    choosing a different variant.

    @return [Array<Hash>] {company, hidden, total, tags}
    """
    out = []
    for role in roles:
        bullets = role.get("bullets") or []
        hidden = [b for b in bullets if not _eligible(b, shape, domain)]
        if not hidden or len(hidden) < MIN_WITHHELD:
            continue
        tags = sorted({t for b in hidden for t in (b.get("shapes") or [])})
        out.append({"company": role.get("company", "?"), "hidden": len(hidden),
                    "total": len(bullets), "tags": tags})
    return out


def requirements(job):
    """The posting's stated asks, taken only from where it states them.

    Only list items under a requirements-style heading count. Treating every
    sentence as a requirement produces a gap list full of "we are a company",
    and a gap list nobody believes is worse than none.

    @return [Array<String>] verbatim, deduplicated, in the posting's own order
    """
    text = job.get("description") or ""
    if not text:
        return []

    if "<li" in text.lower() or "<h" in text.lower():
        return _html_requirements(text)

    out, seen = [], set()
    for m in REQUIREMENT_HEADING.finditer(text):
        # A requirements list runs until the next blank-line-separated heading.
        section = text[m.end():]
        end = re.search(r"\n\s*\n\s*\w[^\n]{0,60}:\s*\n", section)
        if end:
            section = section[:end.start()]
        for line in BULLET_LINE.findall(section):
            item = " ".join(line.split())
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def _corpus(facts):
    """@return [Array<Tuple(str, set)>] every piece of evidence and its terms."""
    entries = []
    for group in facts.get("skill_groups") or []:
        for term in group.get("terms") or []:
            entries.append((term, _terms(term) or {term.lower()}))
    for role in facts.get("roles") or []:
        for b in role.get("bullets") or []:
            entries.append((b.get("text", ""), _terms(b.get("text"))))
    for p in facts.get("projects") or []:
        entries.append((p.get("text", ""), _terms(p.get("text"))))
    return entries


# A term appearing in more than this share of the resume's entries says nothing
# about any particular requirement. "developed", "platform" and "production" are
# in most bullets; the ask lives in the rare word.
GENERIC_SHARE = 0.34
# A term in more than this share of job postings is the genre's boilerplate:
# "experience", "team", "professional". Below it, the term is the actual ask.
MARKET_ASK_SHARE = 0.25
# A term in fewer than this share is almost certainly a typo or a proper noun
# from one company, not a skill anyone is asking for.
MARKET_FLOOR = 0.0005
# Covered means every specific term is answered. A fraction was tried first and
# a half-answered requirement fell exactly on the boundary and read as covered —
# but the whole value of the section is naming what is missing, so any unanswered
# specific ask makes it partial and gets named.


# Proper nouns that are not technologies. Capitalisation alone would read these
# as named tools.
NOT_TECH = {
    "english", "spanish", "french", "german", "we", "our", "you", "your", "i",
    "monday", "friday", "us", "eu", "uk", "usa", "america", "european",
    "bachelor", "master", "phd", "bs", "ms", "ba", "ma",
}
# Words that open a requirement line by grammar rather than by being a name.
# Measured across 10,195 requirement lines in the corpus: these are the framing
# words, in frequency order. Excluding EVERY capitalised opener instead threw
# away the technology whenever a line began with it — "Rails experience",
# "Kubernetes in production" — which is a common way to write one.
REQUIREMENT_OPENERS = {
    "experience", "strong", "ability", "a", "an", "the", "you", "your", "proven",
    "familiarity", "demonstrated", "excellent", "deep", "proficiency", "hands-on",
    "prior", "background", "comfort", "comfortable", "knowledge", "bachelor",
    "demonstrates", "track", "have", "has", "exceptional", "high", "clear",
    "understanding", "are", "is", "solid", "working", "expertise", "skilled",
    "passion", "passionate", "willingness", "eagerness", "desire", "must",
    "should", "we", "our", "in", "at", "as", "with", "and", "or", "self",
    "excited", "curious", "committed", "able", "capable", "fluent", "adept",
    "extensive", "significant", "substantial", "several", "minimum", "at-least",
    # The tail of the same measurement: verbs and adjectives that open a
    # requirement line. Anything NOT here in that position is read as a name,
    # which is what lets "Rails experience" and "Kubernetes in production" work.
    "care", "cares", "uphold", "bring", "brings", "can", "enjoy", "enjoys",
    "thrive", "thrives", "possess", "stay", "communicate", "collaborate",
    "advanced", "analytical", "collaborative", "communication", "curiosity",
    "detail-oriented", "direct", "effective", "experienced", "expert", "exposure",
    "fluency", "genuine", "good", "highly", "history", "interest", "motivation",
    "openness", "operational", "outstanding", "practical", "preferred",
    "previous", "professional", "proficient", "self-starter", "skill", "some",
    "sound", "strategic", "superior", "technical", "this", "thorough", "work",
    "adaptability", "alignment", "people", "project", "systems", "data-driven",
}
SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n\s*)([A-Z][\w+#.-]*)")
# Kubernetes, Terraform, Go, Node.js, C#, C++, CI/CD.
PROPER_NOUN = re.compile(r"\b([A-Z][a-zA-Z0-9]*(?:[+#]|\.[a-zA-Z]+)?)\b")
ACRONYM = re.compile(r"\b([A-Z]{2,6})\b")
# "7+ years", "5 years". A bare number is a version, not a duration.
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?years?\b", re.I)


_MIDSENTENCE = None


def checkable(requirement):
    """What in this requirement can actually be checked.

    A technology or proper noun, a quantity of years, a credential — those are
    answerable. A disposition is not: "strong communication" and "cares about
    societal impact" name nothing anyone can verify against a resume, and
    reporting them as gaps produced a list entirely of soft skills while every
    hard ask came back met.

    @param requirement [String] verbatim, with its capitalisation intact
    @return [Hash] {tech, years}
    """
    text = requirement or ""
    # Only a measured framing word is dropped for opening the line. Anything else
    # in that position is a name — a line may legitimately begin with its subject.
    openers = {m.group(1).lower() for m in SENTENCE_START.finditer(text)
               if m.group(1).lower() in REQUIREMENT_OPENERS}
    tech = set()
    for m in PROPER_NOUN.finditer(text):
        word = m.group(1)
        low = word.lower()
        if low in openers or low in NOT_TECH or low in STOP or len(low) < MIN_NAME_CHARS:
            continue
        tech.add(low)
    for m in ACRONYM.finditer(text):
        low = m.group(1).lower()
        if low not in NOT_TECH and low not in STOP:
            tech.add(low)

    years = YEARS.search(text)
    return {"tech": tech, "years": int(years.group(1)) if years else None}


def is_actionable(requirement):
    """@return [Boolean] whether this ask names anything that can be checked."""
    found = checkable(requirement)
    return bool(found["tech"]) or found["years"] is not None


def _matches(want, have):
    """Terms that name the same thing, allowing for how people write them.

    Exact token equality reports "PostgreSQL tuning" as unmatched by a skill
    listed as "postgres", which is a false gap — and a gap list carrying false
    gaps is worse than no gap list, because the one section that decides
    anything stops being believed.

    @return [set<str>] the terms from `want` that are answered by `have`
    """
    hit = set()
    for w in want:
        if any(_same_word(w, h) for h in have):
            hit.add(w)
    return hit


def _same_word(a, b):
    """Whether two terms are the same word written differently.

    A shared prefix alone matched "java" to "javascript", reporting a Java
    requirement as met by JavaScript experience. A morphological variant differs
    by an ending, not by six characters, so the length gap is bounded.
    """
    if a == b:
        return True
    if min(len(a), len(b)) < STEM_MIN:
        return False
    return (a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) <= MAX_STEM_GAP


def years_from(facts, today=None):
    """Total professional experience, in years, from the dated roles.

    Overlapping roles are merged rather than summed: running a company alongside
    a job is not twice the experience, and adding them would answer "7+ years"
    with a number nobody would recognise.

    @return [Float, nil] nil when no role carries dates
    """
    today = today or datetime.now(timezone.utc).date()
    spans = []
    for role in facts.get("roles") or []:
        start, end = role.get("start"), role.get("end")
        if not start:
            continue
        try:
            s_y, s_m = (int(x) for x in str(start).split("-")[:2])
            if not end or str(end).lower() in ("present", "current", "now"):
                e_y, e_m = today.year, today.month
            else:
                e_y, e_m = (int(x) for x in str(end).split("-")[:2])
        except (ValueError, TypeError):
            continue
        spans.append((s_y * 12 + s_m, e_y * 12 + e_m))
    if not spans:
        return None

    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return round(sum(b - a for a, b in merged) / 12, 1)


def evidence(reqs, facts, years_of_experience=None):
    """Match each stated requirement, and be honest about how well.

    ONLY CHECKABLE ASKS COUNT. An earlier version decided what a requirement asked
    for from how rare its terms were across the corpus, which inverts on a tech
    corpus: Kubernetes, AWS and Terraform appear in many postings BECAUSE they
    matter, so rarity classified them as boilerplate and dropped them, while
    "societal impacts and ethics" survived by being unusual. Every hard ask on a
    real posting came back met and the gap list was entirely soft skills.

    A technology, a proper noun or a quantity of years can be checked against a
    resume. A disposition cannot, and is neither a gap nor a partial — reporting
    "strong communication" as unmet gives him nothing to act on.

    @param years_of_experience [Float, nil] defaults to the dated roles in facts
    @return [Array(Array<Hash>, Array<String>)] (matched, gaps)
    """
    if not reqs:
        return [], []

    corpus = _corpus(facts)
    have_years = years_of_experience
    if have_years is None:
        have_years = years_from(facts)

    matched, gaps = [], []
    for req in reqs:
        asks = checkable(req)
        tech, wants_years = asks["tech"], asks["years"]

        if not tech and wants_years is None:
            # A disposition. Not answerable, so not a gap.
            matched.append({"requirement": req, "evidence": [], "soft": True})
            continue

        hits, answered = [], set()
        for text, terms in corpus:
            shared = _matches(tech, terms)
            if shared:
                hits.append((len(shared), text))
                answered |= shared

        missing = sorted(tech - answered)
        if wants_years is not None and have_years is not None and have_years < wants_years:
            missing.append(f"{wants_years}+ years (you have about {have_years:g})")

        if not answered and missing:
            gaps.append(req)
            continue

        hits.sort(key=lambda h: -h[0])
        entry = {"requirement": req,
                 "evidence": [t for _, t in hits[:EVIDENCE_PER_REQUIREMENT]]}
        if missing:
            entry["partial"] = True
            entry["missing"] = missing
        matched.append(entry)

    return matched, gaps


def friction(url):
    """How much of an evening this application will cost.

    @return [String] low | high | unknown
    """
    host = (urlparse(url or "").hostname or "").lower()
    for level, hosts in FRICTION.items():
        if any(host.endswith(h) or h in host for h in hosts):
            return level
    return "unknown"


def _header(job, decision):
    out = [f"{job.get('company', '?')} — {job.get('title', '?')}", ""]
    if decision:
        out.append(f"variant   {decision.get('variant', '?')}")
        out.extend(f"          {r}" for r in decision.get("reasons", [])[:2])
    else:
        out.append("variant   not determined")
    flags = (decision or {}).get("flags") or []
    if flags:
        out.append("flags     " + "; ".join(f"{n}: {why}" for n, why in flags))
    out.append(f"apply     {job.get('url', '?')}  ({friction(job.get('url'))} friction)")
    out.append("")
    return out


def _partial_section():
    """Deliberately prints nothing, and the reason is worth keeping.

    A third state between covered and gap is real — he has the Rails, not the
    Kubernetes — and the data for it is computed and returned on each match. It is
    not PRINTED because the missing terms cannot yet be told apart from ordinary
    English: measured across 943 postings' requirement text, "fundamentals" (.030)
    and "proficient" (.019) sit in the same frequency band as "kubernetes" (.048)
    and "terraform" (.018), so the section rendered as "missing: e.g, nobody,
    possible, thing".

    Separating a real unmet ask from prose needs a signal frequency alone does not
    give. Until there is one, showing this costs more than it gives: GAPS is the
    section that decides anything, and burying it under noise is how it stops
    being read.
    """
    return []


def _gaps_section(gaps):
    if not gaps:
        return []
    # First, because it is the only section that decides anything.
    return ["GAPS — asked for, and nothing in the resume answers it",
            *[f"  · {g}" for g in gaps], ""]


def _evidence_section(matched):
    if not matched:
        return []
    out = ["EVIDENCE — their ask, your material"]
    for m in matched:
        out.append(f"  {m['requirement']}")
        out.extend(f"      {e[:96]}" for e in m["evidence"])
    out.append("")
    return out


def _withheld_section(held, decision):
    if not held:
        return []
    variant = (decision or {}).get("variant", "this")
    out = [f"WITHHELD — tagged out of the {variant} variant"]
    for h in held:
        out.append(f"  · {h['company']}: {h['hidden']} of {h['total']} bullets "
                   f"tagged {', '.join(h['tags'])}")
    out.append("    Widen a tag in resume.toml, or pick a different variant.")
    out.append("")
    return out


def _bullets_section(bullets):
    if not bullets:
        return []
    out = ["BULLETS — ranked against this posting, in authoring order"]
    for company, title, chosen in bullets:
        out.append(f"  {company} — {title}")
        out.extend(f"      {b.get('text', '')[:96]}" for b in chosen)
    out.append("")
    return out


def brief(job, facts, decision=None):
    """One page to write an application FROM.

    Assembled from sections rather than one long branch, so each part is testable
    on its own and the order of the page is visible in one place. The gaps come
    first because they are the only section that decides anything; everything
    else saves time once that decision is made.

    @param job [Hash] the posting
    @param facts [Hash] resume.toml
    @param decision [Hash, nil] gate.decide output, when available
    @return [String]
    """
    reqs = requirements(job)
    matched, gaps = evidence(reqs, facts)
    shape = (decision or {}).get("shape")
    domain = (decision or {}).get("domain")
    roles = facts.get("roles") or []

    out = _header(job, decision)
    out += _gaps_section(gaps)
    out += _partial_section()
    out += _evidence_section([m for m in matched if not m.get("partial")])
    out += _withheld_section(withheld(roles, shape, domain), decision)
    out += _bullets_section(bullets_for(roles, job, shape, domain))

    if not reqs:
        out.append("This posting states no requirements list, so there is nothing to")
        out.append("match against and no gap analysis. Read it yourself.")
    return "\n".join(out)
