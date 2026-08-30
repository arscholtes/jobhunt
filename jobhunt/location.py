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
SPLIT = re.compile(r"[;|]|\bor\b", re.I)


def _parts(chunk):
    return [p.strip().lower().strip(".") for p in chunk.split(",") if p.strip()]


def _classify_one(chunk):
    parts = _parts(chunk)
    if not parts:
        return "unknown"
    if any(p in US_NAMES for p in parts):
        return "domestic"
    for p in parts:
        if p in COUNTRIES:
            return "international"
    for p in parts:
        if p in US_STATES or p in US_ABBR:
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
        for p in _parts(chunk):
            if p in COUNTRIES:
                return p.title()
    return None
