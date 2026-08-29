"""Generate one resume variant from the canonical facts.

The matrix is generated, not maintained. Every cell is a *selection and
ordering* of resume.toml, so there is exactly one copy of each fact and
correcting it once corrects it everywhere. Hand-maintaining the same eight
documents would mean applying every correction eight times and discovering the
one you missed in an interview.

Construction is fixed across all cells and is the one part not up for tuning,
because it defends against the only resume failure that is actually measured:
two-column layouts scrambled in 7 of 8 ATS parsers tested, table content
dropped in 5 of 8, header/footer text ignored, and image-based text losing name
and contact details every time. So: single column, no tables, no sidebars,
contact in the body, standard section headings, real text.

What varies per cell is which evidence leads — not how it is laid out.
"""
import pathlib, tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "resume.toml"
EXAMPLE = ROOT / "resume.example.toml"

BULLETS_PER_ROLE = 5

# Terms to float to the front of their skill group for a given axis. Membership
# never changes — a variant reorders the evidence, it does not invent or hide it.
PRIORITY = {
    "backend":   ["ruby", "rails", "postgres", "sql", "sidekiq", "redis", "rest", "webhook", "multi-tenan", "event-driven"],
    "platform":  ["event-driven", "sidekiq", "docker", "opentelemetry", "multi-tenan", "code review", "test-driven"],
    "fullstack": ["ruby on rails", "hotwire", "react", "typescript", "javascript", "postgres"],
    "fde":       ["webhook", "rest", "integration", "sql", "postgres", "python", "docker"],
    "generic":   [],
    "ai":        ["python", "opentelemetry", "event-driven", "rest", "webhook"],
    "devtools":  ["typescript", "node", "docker", "rest", "code review", "test-driven"],
    "rails":     ["ruby", "ruby on rails", "rails", "rspec", "sidekiq", "hotwire", "postgres"],
    "general":   [],
}


class ResumeError(RuntimeError):
    pass


def load(path=None):
    p = pathlib.Path(path) if path else PATH
    if not p.exists():
        raise ResumeError(
            f"No resume facts at {p}. Copy {EXAMPLE.name} to {p.name} and fill it in."
        )
    with p.open("rb") as fh:
        data = tomllib.load(fh)
    for key in ("me", "summaries"):
        if key not in data:
            raise ResumeError(f"{p.name} is missing required section [{key}]")
    data.setdefault("roles", [])
    data.setdefault("projects", [])
    data.setdefault("skill_groups", [])
    data.setdefault("education", {"show": False, "lines": []})
    return data


def _eligible(item, shape, domain):
    shapes, domains = item.get("shapes") or [], item.get("domains") or []
    return (not shapes or shape in shapes) and (not domains or domain in domains)


def _rank(item, shape, domain):
    """Weight first, relevance as the tiebreaker.

    Tags decide *eligibility*; weight decides *order*. An earlier version added a
    flat bonus for a shape or domain match, which let three tagged weight-8
    bullets push out an untagged weight-10 one — relevance outranking your own
    judgment of what your best material is. An untagged bullet is eligible
    everywhere, which is not a reason to rank it last.
    """
    return (item.get("weight", 5),
            shape in (item.get("shapes") or []),
            domain in (item.get("domains") or []))


def _select(items, shape, domain, limit=None):
    keep = [i for i in items if _eligible(i, shape, domain)]
    keep.sort(key=lambda i: _rank(i, shape, domain), reverse=True)
    return keep[:limit] if limit else keep


def summary(facts, shape, domain):
    """Most specific summary available: 'shape.domain', then shape, then default."""
    table = facts["summaries"]
    for key in (f"{shape}.{domain}", shape, "default"):
        if key in table:
            return table[key]
    return ""


def skills(facts, shape, domain):
    """Reorder groups and terms by relevance. Nothing is added or removed."""
    priority = PRIORITY.get(shape, []) + PRIORITY.get(domain, [])

    def term_key(term):
        low = term.lower()
        for i, p in enumerate(priority):
            if p in low:
                return i
        return len(priority)

    groups = []
    for group in facts["skill_groups"]:
        terms = sorted(group["terms"], key=term_key)
        lead = min((term_key(t) for t in group["terms"]), default=len(priority))
        groups.append((lead, {"name": group["name"], "terms": terms}))
    groups.sort(key=lambda g: g[0])
    return [g for _, g in groups]


def build(facts, shape, domain):
    """Assemble one variant as structured content, ready to render."""
    roles = []
    for role in facts["roles"]:
        bullets = _select(role.get("bullets", []), shape, domain, BULLETS_PER_ROLE)
        if not bullets:
            continue
        roles.append({**role, "bullets": bullets})
    return {
        "me": facts["me"],
        "variant": f"{shape}.{domain}",
        "summary": summary(facts, shape, domain),
        "skills": skills(facts, shape, domain),
        "roles": roles,
        "projects": _select(facts["projects"], shape, domain, 3),
        "education": facts.get("education", {}),
    }


def render(doc):
    """Parse-safe Markdown: single column, no tables, contact details in the body."""
    me = doc["me"]
    out = [f"# {me['name']}", ""]

    contact = [me.get("location"), me.get("email"), me.get("phone"),
               me.get("github"), me.get("linkedin"), me.get("site")]
    out += [" | ".join(c for c in contact if c), ""]

    if doc["summary"]:
        out += ["## Summary", "", doc["summary"], ""]

    if doc["skills"]:
        out += ["## Skills", ""]
        out += [f"{g['name']}: {', '.join(g['terms'])}" for g in doc["skills"]]
        out += [""]

    def _section(heading, roles):
        if not roles:
            return []
        block = [f"## {heading}", ""]
        for role in roles:
            dates = f"{role.get('start', '')} - {role.get('end', '')}".strip(" -")
            block += [f"### {role['title']}, {role['company']}",
                      f"{dates}" + (f" | {role['location']}" if role.get("location") else ""), ""]
            block += [f"- {b['text']}" for b in role["bullets"]]
            block += [""]
        return block

    # Two sections, each newest first. Employment leads because that is what a
    # hiring reader scans for; the founder thread reads as one story below it.
    def _recency(r):
        return str(r.get("end") or "9999")
    roles = doc["roles"]
    out += _section("Experience", sorted(
        [r for r in roles if r.get("kind", "employment") != "founder"], key=_recency, reverse=True))
    out += _section("Founder & Operator", sorted(
        [r for r in roles if r.get("kind") == "founder"], key=_recency, reverse=True))

    if doc["projects"]:
        out += ["## Projects", ""]
        for p in doc["projects"]:
            url = f" ({p['url']})" if p.get("url") else ""
            out += [f"- {p['name']}{url}: {p['text']}"]
        out += [""]

    edu = doc["education"]
    if edu.get("show") and edu.get("lines"):
        out += ["## Education", ""] + list(edu["lines"]) + [""]

    return "\n".join(out).rstrip() + "\n"


def generate(shape, domain, facts=None):
    return render(build(facts or load(), shape, domain))
