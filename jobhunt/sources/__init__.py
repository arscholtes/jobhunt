"""Job board adapters.

Each adapter exposes `fetch(company_token) -> list[dict]` returning rows shaped
for `store.upsert_jobs`. All six boards below publish read-only JSON endpoints
intended for exactly this use.

Five are applicant-tracking systems, where the token addresses one company's
board. IndyHackers is a community board for a single metro: its token addresses
a collection rather than a company, and it is the only source that knows where
its postings are without being told.
"""
from . import ashby, greenhouse, indyhackers, lever, smartrecruiters, workable

ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
            "workable": workable, "smartrecruiters": smartrecruiters,
            "indyhackers": indyhackers}


def fetch(source, token):
    try:
        adapter = ADAPTERS[source]
    except KeyError:
        raise ValueError(f"unknown source {source!r}; expected one of {', '.join(ADAPTERS)}") from None
    return adapter.fetch(token)
