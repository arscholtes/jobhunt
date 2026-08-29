"""Greenhouse public job board API."""
import re

from ._http import get_json

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
TAG = re.compile(r"<[^>]+>")


def _text(html):
    if not html:
        return ""
    import html as htmlmod
    return htmlmod.unescape(TAG.sub(" ", html)).replace("\xa0", " ")


def fetch(token):
    payload = get_json(API.format(token=token))
    rows = []
    for j in payload.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        rows.append({
            "id": f"greenhouse:{token}:{j['id']}",
            "source": "greenhouse",
            "company": token,
            "title": j.get("title", ""),
            "location": loc,
            "remote": 1 if "remote" in loc.lower() else 0,
            "url": j.get("absolute_url", ""),
            "description": " ".join(_text(j.get("content", "")).split()),
            "posted_at": j.get("updated_at"),
        })
    return rows
