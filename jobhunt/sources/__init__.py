"""Job board adapters.

Each adapter exposes `fetch(company_token) -> list[dict]` returning rows shaped
for `store.upsert_jobs`. All five boards below publish read-only JSON endpoints
intended for exactly this use.
"""
from . import ashby, greenhouse, lever, smartrecruiters, workable

ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
            "workable": workable, "smartrecruiters": smartrecruiters}


def fetch(source, token):
    try:
        adapter = ADAPTERS[source]
    except KeyError:
        raise ValueError(f"unknown source {source!r}; expected one of {', '.join(ADAPTERS)}")
    return adapter.fetch(token)
