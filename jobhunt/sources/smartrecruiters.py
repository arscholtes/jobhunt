"""SmartRecruiters public postings API.

The list endpoint returns summaries without a description, so each posting needs
a second call for its body. That is slow but the descriptions are what the
signal extraction reads, and a posting without one scores as if it mentioned
nothing at all — worse than being absent.
"""
from ._http import get_json

LIST = "https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}"
DETAIL = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{pid}"


def _body(token, pid):
    """Flatten the nested jobAd sections into one blob of text."""
    try:
        d = get_json(DETAIL.format(token=token, pid=pid))
    except Exception:
        return ""
    sections = (d.get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(key) or {}).get("text") or ""
        if text:
            parts.append(text)
    return " ".join(" ".join(parts).split())


def fetch(token, max_postings=200):
    rows, offset = [], 0
    while offset < max_postings:
        payload = get_json(LIST.format(token=token, offset=offset))
        batch = payload.get("content") or []
        if not batch:
            break
        for j in batch:
            loc = j.get("location") or {}
            where = ", ".join(p for p in (loc.get("city"), loc.get("region"), loc.get("country")) if p)
            remote = 1 if loc.get("remote") or "remote" in where.lower() else 0
            rows.append({
                "id": f"smartrecruiters:{token}:{j['id']}",
                "source": "smartrecruiters",
                "company": (j.get("company") or {}).get("name") or token,
                "title": j.get("name", ""),
                "location": where,
                "remote": remote,
                "url": (j.get("ref") or "").replace("api.smartrecruiters.com/v1", "jobs.smartrecruiters.com")
                       or f"https://jobs.smartrecruiters.com/{token}/{j['id']}",
                "description": _body(token, j["id"]),
                "posted_at": j.get("releasedDate"),
            })
        offset += len(batch)
        if len(batch) < 100:
            break
    return rows
