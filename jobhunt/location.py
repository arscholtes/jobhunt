"""Where a posting is, and whether that is a preference or a visa.

score.py treated "Dublin, Ireland" exactly as "Denver, Colorado" — both fell to
elsewhere_weight and collected the same fraction of the location points. The
comment justifying that says relocating is a tradeoff against comp rather than a
hard no, which is true of a domestic move and false of one that needs work
authorisation. They are different in kind, and the code did not distinguish them.

Nothing is excluded here. Some of these companies sponsor, and whether that is
worth pursuing is his call. The job of this module is only to stop an
international posting outranking a domestic one by accident.

Read from the location field, which names the country plainly, rather than
inferred from the description. gate.flags' REGION_LOCK looks for "[Canada]" title
tags and "EMEA only" phrasing and misses every one of these.
"""

from __future__ import annotations

import re

# US states and their abbreviations. A posting naming one is reachable.
US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia", "washington dc", "washington d.c.",
}
US_ABBR = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
    "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
}
US_NAMES = {"united states", "usa", "u.s.", "u.s.a.", "us"}

# Countries that appear in these boards' location fields. Not exhaustive by
# design: an unrecognised place is unknown, never penalised.
COUNTRIES = {
    "ireland", "england", "scotland", "wales", "united kingdom", "uk",
    "canada", "brazil", "brasil", "germany", "france", "spain", "portugal",
    "netherlands", "belgium", "denmark", "sweden", "norway", "finland",
    "poland", "czechia", "czech republic", "austria", "switzerland", "italy",
    "greece", "romania", "hungary", "bulgaria", "croatia", "serbia",
    "australia", "new zealand", "japan", "singapore", "india", "china",
    "hong kong", "korea", "south korea", "taiwan", "israel", "mexico",
    "argentina", "chile", "colombia", "peru", "uruguay", "costa rica",
    "south africa", "nigeria", "kenya", "egypt", "turkey", "ukraine",
    "philippines", "vietnam", "thailand", "malaysia", "indonesia",
    "united arab emirates", "uae", "emea", "apac", "latam",
}
SPLIT = re.compile(r"[;|]", re.I)
# Remote is a work ARRANGEMENT, not a place. Matching the field as one string let
# the word defeat the place beside it in both directions — "Argentina Remote"
# stopped being international and "Remote U.S." stopped being domestic. Neither
# was misfiled; both stopped being classified at all, which is worse, because
# unknown is treated as domestic and carries no flag.
ARRANGEMENTS = (
    ("remote", re.compile(r"\b(remote|wfh|work from home|distributed)\b", re.I)),
    ("hybrid", re.compile(r"\bhybrid\b", re.I)),
    ("onsite", re.compile(r"\b(on-?site|in-?office|in person)\b", re.I)),
)
ARRANGEMENT_WORDS = re.compile(
    r"\b(remote|wfh|work from home|distributed|hybrid|on-?site|in-?office|"
    r"in person|only|friendly|first|eligible|based)\b", re.I)
# Periods go too: "U.S." must normalise to "us", or the trailing boundary
# never matches and the most common domestic phrasing reads as unknown.
PUNCT = re.compile(r"[^a-z0-9 ]+")
# Countries written as several words, checked before single tokens so "united
# kingdom" is not read as two unknowns.
MULTIWORD = tuple(sorted((c for c in COUNTRIES if " " in c), key=len, reverse=True))
MULTIWORD_STATES = tuple(sorted((c for c in US_STATES if " " in c), key=len, reverse=True))


def arrangement(text):
    """How the job is worked, independent of where it is.

    @return [String, nil] remote | hybrid | onsite
    """
    for name, pattern in ARRANGEMENTS:
        if pattern.search(text or ""):
            return name
    return None


def _words(chunk):
    """@return [String] lowercased, depunctuated, arrangement words removed."""
    plain = ARRANGEMENT_WORDS.sub(" ", chunk or "").lower()
    # Periods are DELETED rather than spaced: "u.s." must become "us", and
    # replacing them with spaces yields "u s", which matches nothing.
    plain = plain.replace(".", "")
    plain = PUNCT.sub(" ", plain)
    return " ".join(plain.split())


def _has(text, terms):
    return any(re.search(rf"\b{re.escape(t)}\b", text) for t in terms)


def _classify_one(chunk):
    """Classify one location alternative, place only.

    A US signal wins over a foreign one within a single alternative — "Remote (US
    or Canada)" is reachable, because he can take the US side.
    """
    text = _words(chunk)
    if not text:
        return "unknown"

    if _has(text, US_NAMES) or _has(text, MULTIWORD_STATES):
        return "domestic"

    foreign = _has(text, MULTIWORD) or _has(text, COUNTRIES - set(MULTIWORD))
    if foreign:
        # Two-letter abbreviations are ambiguous — "or" is both Oregon and a
        # conjunction, and Canadian provinces sit in the same lists. A named
        # country outranks them.
        return "international"
    if _has(text, US_STATES) or _has(text, US_ABBR):
        return "domestic"
    return "unknown"


def classify(text):
    """Where this posting can be worked from.

    A posting listing several offices is reachable if ANY of them is domestic —
    he can take the US one — so a mixed list is domestic rather than a compromise.

    @param text [String, nil] the posting's location field
    @return [String] domestic | international | unknown
    """
    if not text or not text.strip():
        return "unknown"
    verdicts = [_classify_one(c) for c in SPLIT.split(text) if c.strip()]
    if "domestic" in verdicts:
        return "domestic"
    if "international" in verdicts:
        return "international"
    return "unknown"


def country(text):
    """@return [String, nil] the foreign country named, for a readable flag."""
    if not text:
        return None
    for chunk in SPLIT.split(text):
        words = _words(chunk)
        if not words:
            continue
        for name in MULTIWORD:
            if re.search(rf"\b{re.escape(name)}\b", words):
                return name.title()
        for name in sorted(COUNTRIES - set(MULTIWORD)):
            if re.search(rf"\b{re.escape(name)}\b", words):
                return name.title()
    return None
