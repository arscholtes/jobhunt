"""Greenhouse public job board API."""
from ._http import get_json, text

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(token):
    payload = get_json(API.format(token=token))
    rows = []
    for j in payload.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        rows.append({
            "id": f"greenhouse:{token}:{j['id']}",
            "source": "greenhouse",
            "company": token,
            "title": j.get("title", ""),
            "location": loc,
            "remote": 1 if "remote" in loc.lower() else 0,
            "url": j.get("absolute_url", ""),
            "description": text(j.get("content")),
            "posted_at": j.get("updated_at"),
        })
    return rows
