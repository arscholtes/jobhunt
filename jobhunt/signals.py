"""Signals a posting reveals about itself, beyond title and stack.

The base score answers "does this posting match what I do". These answer "is this
a room I would do well in" — which for some candidates matters more than the stack.

Same philosophy as score.py: transparent patterns, every finding traceable to a
phrase in the posting. A wrong signal is a pattern you can fix, not a model you
have to trust. Everything here degrades to "unknown" rather than guessing.
"""
import re
import urllib.parse

# How a company interviews is often stated outright, and it predicts fit better
# than the stack does. A timed live-coding screen and a take-home select for
# very different people.
INTERVIEW = [
    ("take_home", r"take[- ]home|async (?:exercise|assignment)|project we send|work sample"),
    ("pairing", r"pair(?:ing)? (?:session|program|exercise)|pair with (?:an? )?engineer|collaborative coding"),
    ("live_coding", r"live[- ]cod|whiteboard|technical screen|coding (?:challenge|interview|screen)|hackerrank|codesignal|karat"),
    ("system_design", r"system design|architecture (?:interview|discussion)|design interview"),
    ("no_leetcode", r"no (?:leetcode|whiteboard|trick questions|algorithm puzzles)|we do ?n[o']t (?:do )?leetcode"),
]

# Whether they say anything about AI tooling. Silence is not neutral — it usually
# means the question gets decided in the room by whoever interviews you.
AI_STANCE = [
    ("encouraged", r"\b(?:copilot|cursor|claude code|claude|chatgpt|llm tooling|ai[- ]assisted|ai tools?)\b[^.]{0,80}\b(?:encourag|expect|provide|licen[cs]e|welcome|embrace|use)"),
    ("prohibited", r"(?:no|not permitted|prohibited|without)\s+(?:use of\s+)?(?:ai|copilot|chatgpt|llm)[^.]{0,40}(?:during|in the|for the)\s+interview|ai[- ]free interview"),
    ("mentioned", r"\b(?:copilot|cursor|claude|chatgpt|llm|generative ai|ai[- ]assisted)\b"),
]

# Published compensation. Several US states mandate it, so its absence in those
# markets is itself weak signal.
COMP = re.compile(
    r"\$\s?(\d{2,3})(?:,\d{3}|k)\s*(?:-|–|to)\s*\$?\s?(\d{2,3})(?:,\d{3}|k)", re.I
)

# Application friction, inferred from where the apply link lands. A two-field
# Ashby form and a 40-minute Workday account are not the same cost.
FRICTION = {
    "low": ("ashbyhq.com", "greenhouse.io", "lever.co", "workable.com"),
    "medium": ("smartrecruiters.com", "breezy.hr", "rippling.com", "jobvite.com"),
    "high": ("myworkdayjobs.com", "workday.com", "taleo.net", "icims.com", "successfactors"),
}

# The board a posting was fetched from, when its apply link does not say.
SOURCE_FRICTION = {
    "greenhouse": "low", "lever": "low", "ashby": "low", "workable": "low",
    "smartrecruiters": "medium",
}

STACK = {
    "ruby": r"\bruby\b|\brails\b", "javascript": r"\bjavascript\b|\bnode\b|\breact\b|\bvue\b",
    "typescript": r"\btypescript\b", "python": r"\bpython\b|\bdjango\b|\bfastapi\b",
    "go": r"\bgolang\b|\bgo\b(?= developer| engineer)", "java": r"\bjava\b(?!script)",
    "csharp": r"\bc#\b|\.net\b", "swift": r"\bswift\b|\bios\b",
    "elixir": r"\belixir\b|\bphoenix\b", "rust": r"\brust\b",
}


def _find(patterns, text):
    return [name for name, pat in patterns if re.search(pat, text, re.I)]


def extract(job):
    """Return a dict of signals for one posting. Unknown beats guessed."""
    body = (job.get("description") or "") + " " + (job.get("title") or "")
    url = job.get("url") or ""
    host = urllib.parse.urlparse(url).netloc.lower()

    formats = _find(INTERVIEW, body)
    stance = next((s for s in _find(AI_STANCE, body)), None)

    friction = "unknown"
    for level, hosts in FRICTION.items():
        if any(h in host for h in hosts):
            friction = level
            break
    if friction == "unknown":
        # A company-hosted careers page in front of an ATS form — brex.com,
        # careers.datadoghq.com — has an unrecognisable host and a perfectly
        # knowable form behind it. The row records which board it was fetched
        # from, and that is authoritative in a way the URL is not.
        friction = SOURCE_FRICTION.get(job.get("source"), "unknown")

    comp = COMP.search(body)
    comp_low = int(comp.group(1)) if comp else None
    comp_high = int(comp.group(2)) if comp else None

    return {
        "interview": formats or ["unknown"],
        "ai_stance": stance or "silent",
        "comp_low": comp_low,
        "comp_high": comp_high,
        "friction": friction,
        "stack": [k for k, pat in STACK.items() if re.search(pat, body, re.I)],
    }


def bonus(sig, profile):
    """Points to add or subtract, and why. Returns (delta, reasons).

    Configured under [signals] in profile.toml; absent means zero, so this is
    strictly opt-in and never silently changes an existing ranking.
    """
    cfg = profile.get("signals", {})
    if not cfg:
        return 0.0, []

    delta, why = 0.0, []

    for fmt in sig["interview"]:
        pts = cfg.get(f"interview_{fmt}", 0)
        if pts:
            delta += pts
            why.append(f"{'+' if pts > 0 else ''}{pts} interview:{fmt}")

    pts = cfg.get(f"ai_{sig['ai_stance']}", 0)
    if pts:
        delta += pts
        why.append(f"{'+' if pts > 0 else ''}{pts} ai:{sig['ai_stance']}")

    pts = cfg.get(f"friction_{sig['friction']}", 0)
    if pts:
        delta += pts
        why.append(f"{'+' if pts > 0 else ''}{pts} apply:{sig['friction']}")

    floor = cfg.get("comp_floor")
    if floor and sig["comp_high"]:
        pts = cfg.get("comp_meets_floor", 0) if sig["comp_high"] >= floor else cfg.get("comp_below_floor", 0)
        if pts:
            delta += pts
            why.append(f"{'+' if pts > 0 else ''}{pts} comp:{sig['comp_low']}-{sig['comp_high']}k")

    return round(delta, 1), why
