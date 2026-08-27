"""Ashby public job board API."""
from ._http import get_json

API = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def fetch(token):
    payload = get_json(API.format(token=token))
    rows = []
    for j in payload.get("jobs", []):
        loc = j.get("location") or ""
        rows.append({
            "id": f"ashby:{token}:{j['id']}",
            "source": "ashby",
            "company": token,
            "title": j.get("title", ""),
            "location": loc,
            "remote": 1 if j.get("isRemote") or "remote" in loc.lower() else 0,
            "url": j.get("jobUrl", ""),
            "description": " ".join((j.get("descriptionPlain") or "").split()),
            "posted_at": j.get("publishedAt"),
        })
    return rows
