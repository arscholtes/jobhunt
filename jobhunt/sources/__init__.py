"""Job board adapters.

Each adapter exposes `fetch(company_token) -> list[dict]` returning rows shaped
for `store.upsert_jobs`. All three boards below publish read-only JSON endpoints
intended for exactly this use.
"""
from . import greenhouse, lever, ashby

ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def fetch(source, token):
    try:
        adapter = ADAPTERS[source]
    except KeyError:
        raise ValueError(f"unknown source {source!r}; expected one of {', '.join(ADAPTERS)}")
    return adapter.fetch(token)
