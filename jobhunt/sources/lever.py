"""Lever public postings API."""
from ._http import get_json

API = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch(token):
    rows = []
    for j in get_json(API.format(token=token)):
        cats = j.get("categories") or {}
        loc = cats.get("location") or ""
        wt = (cats.get("commitment") or "") + " " + (j.get("workplaceType") or "")
        rows.append({
            "id": f"lever:{token}:{j['id']}",
            "source": "lever",
            "company": token,
            "title": j.get("text", ""),
            "location": loc,
            "remote": 1 if "remote" in (loc + wt).lower() else 0,
            "url": j.get("hostedUrl", ""),
            "description": " ".join((j.get("descriptionPlain") or "").split()),
            "posted_at": None,
        })
    return rows
