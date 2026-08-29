"""What the daily email carries: the new shortlist, and the pipeline's own state.

THE THRESHOLD is the part that had already failed once. The digest gated on an
absolute score, and stripping per-company boilerplate lowered every score by a
few points — so a bar of 60 that was right when written started withholding good
postings, and the best withheld one missed by 0.2. Nothing reported that the
constant had stopped meaning what it used to mean.

So the gate is a percentile of the scored corpus, which moves when scoring moves,
and the volume is a rank cap, because what a reader wants each morning is the
best few they have not seen rather than everything above a number. The percentile
alone would flood on a good day; the cap alone would send the best of a bad batch
every morning. Both, and neither failure happens.

THE APPLIED SECTION reads the applications table, which has existed since the
first commit and has never been read back in aggregate. Drafted-and-never-sent is
the half of a job search that actually rots, and until now nothing surfaced it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_PERCENTILE = 0.90
DEFAULT_LIMIT = 20
STALE_DRAFT_DAYS = 5
SILENT_SENT_DAYS = 14
RECENT_DAYS = 7
DORMANT = ("rejected", "closed")


def percentile_bar(totals, fraction=DEFAULT_PERCENTILE):
    """The score at a given percentile of everything actually scored.

    Disqualified postings carry -1 as a sentinel and are excluded: they are not
    low scores, they are absences, and letting them into the distribution would
    drag the bar down as the corpus grew.

    @param totals [Array<Float>] every score in the corpus
    @param fraction [Float] 0-1
    @return [Float]
    """
    kept = sorted(t for t in totals if t is not None and t >= 0)
    if not kept:
        return 0.0
    idx = min(int(len(kept) * fraction), len(kept) - 1)
    return float(kept[idx])


def select(rows, bar, limit=DEFAULT_LIMIT):
    """@return [Array] the best `limit` rows at or above `bar`, best first."""
    above = [r for r in rows if r["total"] >= bar]
    above.sort(key=lambda r: -r["total"])
    return above[:limit]


def select_with_overflow(rows, bar, limit=DEFAULT_LIMIT):
    """Same, plus how many qualified and did not fit.

    A posting held back must be counted out loud; silently dropping the tail is
    how a digest starts lying about what it found.

    @return [Array(Array, Integer)]
    """
    above = [r for r in rows if r["total"] >= bar]
    above.sort(key=lambda r: -r["total"])
    return above[:limit], max(0, len(above) - limit)


# --------------------------------------------------------------- the pipeline

def _age_days(iso):
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return 0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).days


def applied_summary(con, stale_days=STALE_DRAFT_DAYS, silent_days=SILENT_SENT_DAYS,
                    recent_days=RECENT_DAYS):
    """What the application pipeline is doing, and what is waiting on a person.

    @param con [sqlite3.Connection]
    @return [Hash] {counts, stale_drafts, silent_sent, recent_rejections}
    """
    rows = con.execute(
        """SELECT a.job_id, a.status, a.updated_at, j.company, j.title, j.url
           FROM applications a JOIN jobs j ON j.id = a.job_id""").fetchall()

    counts, stale, silent, rejected = {}, [], [], []
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        days = _age_days(r["updated_at"])
        entry = {"job_id": r["job_id"], "company": r["company"],
                 "title": r["title"], "url": r["url"], "days": days}
        if r["status"] in DORMANT:
            if r["status"] == "rejected" and days <= recent_days:
                rejected.append(entry)
            continue
        if r["status"] == "drafted" and days >= stale_days:
            stale.append(entry)
        elif r["status"] == "sent" and days >= silent_days:
            silent.append(entry)

    for lst in (stale, silent, rejected):
        lst.sort(key=lambda e: -e["days"])
    return {"counts": counts, "stale_drafts": stale,
            "silent_sent": silent, "recent_rejections": rejected}


def render_applied(summary):
    """Render the applied section, or nothing at all.

    A section with nothing to say says nothing. Printing "nothing to report" in
    every email forever is how a reader learns to skip a section.

    @return [String] "" when the pipeline is empty
    """
    counts = summary.get("counts") or {}
    if not counts:
        return ""

    order = ["interested", "drafted", "sent", "rejected", "closed"]
    line = "  ".join(f"{counts[s]} {s}" for s in order if counts.get(s))
    out = [f"    {line}"]

    for entry, label in ((summary["stale_drafts"], "drafted, not sent"),
                         (summary["silent_sent"], "sent, no reply")):
        for e in entry[:5]:
            out.append(f"      {label} {e['days']}d — {e['company']} {e['title'][:44]}")
    for e in summary["recent_rejections"][:5]:
        out.append(f"      rejected {e['days']}d ago — {e['company']} {e['title'][:44]}")
    return "\n".join(out)
