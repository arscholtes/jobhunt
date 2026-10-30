"""IndyHackers, the Indianapolis community job board.

The 34 ATS feeds are national tech companies. Measured 2026-09-11, exactly one of
5,009 stored postings is located in Indiana, so a local search cannot be fixed by
reweighting: there is nothing local to promote.

This board is different in kind from the five ATS adapters beside it. It runs
PocketBase and serves its jobs collection as public read-only JSON, but a record
carries NO location and NO url — the board is Indiana by charter, and 29 of its
41 live postings name no apply link at all. Both facts are supplied here, so the
rest of the pipeline sees an ordinary row and no other module needs to know this
source is unusual.
"""
import re

from .. import location as location_mod
from ._http import get_json, text

# PocketBase list endpoint. The filter is the board's own notion of a live
# posting; `perPage` is above the whole collection's size, so one page is all of
# it and there is no paging to get wrong.
API = ("https://www.indyhackers.org/api/collections/{token}/records"
       "?perPage=500&sort=-created&filter=(filled=false)")

# A posting has no page of its own: the site is a single-page app whose sitemap
# lists /jobs and no per-record route. The board page is the honest destination.
BOARD = "https://www.indyhackers.org/jobs"

# Every posting here is on an Indiana board. Where the description names no city
# this is what the row says, because the state is what the source guarantees.
DEFAULT_LOCATION = "Indiana"

# The metro, named rather than parsed. A general place-parser over prose finds
# the customer's city and the founder's home town as readily as the job's, and
# this board only ever covers one metro — a list is the smaller claim.
# Indianapolis leads: a posting naming both the city and a suburb is in the metro.
CITIES = ("Indianapolis", "Carmel", "Fishers", "Noblesville", "Westfield",
          "Zionsville", "Greenwood", "Brownsburg", "Avon", "Plainfield",
          "Bloomington", "Lafayette", "Muncie", "Fort Wayne", "Evansville",
          "South Bend")

# Only somewhere a browser can go. 6 of 41 live postings link an email address
# and 29 link nothing, and neither is a URL.
LINK = re.compile(r'href="(https?://[^"]+)"', re.I)


def _place(body):
    """@return [String] "City, Indiana" where one is named, else the state."""
    for city in CITIES:
        if re.search(rf"\b{city}\b", body, re.I):
            return f"{city}, Indiana"
    return DEFAULT_LOCATION


def _live(record):
    """A posting that is still open, per the board's own two flags."""
    return record.get("approved") and not record.get("filled")


def rows(payload, token):
    """Records as postings shaped for `store.upsert_jobs`.

    @param payload [Hash] the PocketBase list response
    @param token [String] the collection name, which is also the board address
    @return [Array<Hash>]
    """
    out = []
    for r in payload.get("items", []):
        if not _live(r):
            continue
        body = text(r.get("description"))
        title = r.get("title", "")
        link = LINK.search(r.get("how_to_apply") or "")
        out.append({
            "id": f"indyhackers:{token}:{r['id']}",
            "source": "indyhackers",
            "company": r.get("company", ""),
            "title": title,
            "location": _place(f"{title} {body}"),
            "remote": 1 if location_mod.remote_in_prose(f"{title}. {body}") else 0,
            "url": link.group(1) if link else BOARD,
            "description": body,
            "posted_at": r.get("created"),
        })
    return out


def fetch(token):
    return rows(get_json(API.format(token=token)), token)
