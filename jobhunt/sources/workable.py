"""Workable public job board API.

Workable exposes a read-only JSON feed per account at a stable path. Postings
carry a structured `location` object rather than a string, and `telecommuting`
is authoritative for remote — more reliable than sniffing the location text.
"""
from ._http import get_json

API = "https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"


def fetch(token):
    payload = get_json(API.format(token=token))
    rows = []
    for j in payload.get("jobs", []):
        loc = j.get("location") or {}
        city = loc.get("city") or ""
        region = loc.get("region") or ""
        country = loc.get("country") or ""
        where = ", ".join(p for p in (city, region, country) if p)
        remote = 1 if loc.get("telecommuting") or "remote" in where.lower() else 0
        rows.append({
            "id": f"workable:{token}:{j.get('shortcode') or j.get('id')}",
            "source": "workable",
            "company": payload.get("name") or token,
            "title": j.get("title", ""),
            "location": where,
            "remote": remote,
            "url": j.get("url") or j.get("application_url") or "",
            "description": " ".join((j.get("description") or "").split()),
            "posted_at": j.get("published_on") or j.get("created_at"),
        })
    return rows
