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

import re

from datetime import datetime, timezone

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


# Location noise only. LEVEL WORDS ARE DELIBERATELY NOT STRIPPED: measured across
# the live shortlist, any similarity threshold loose enough to catch the one real
# near-duplicate also collapsed "Software Engineer, Wallet" into "Senior Software
# Engineer, Wallet" and two distinct teams. Those are different jobs, and a
# collapsed posting is invisible rather than merely mis-ranked — which makes a
# false collapse far more expensive than a missed one.
TITLE_NOISE = re.compile(
    r"[(\[][^)\]]*[)\]]|[-–—,]\s*(remote|hybrid|onsite|[a-z .]+,\s*[a-z]{2})\s*$",
    re.I)


def _normalised_title(title):
    """@return [String] lowercased, depunctuated, location stripped. Level kept."""
    plain = TITLE_NOISE.sub(" ", title or "")
    plain = re.sub(r"[^a-z0-9 ]+", " ", plain.lower())
    return " ".join(plain.split())


def dedupe(rows):
    """Collapse the same job listed more than once, keeping the best instance.

    A posting duplicated per location eats slots the digest is rationing. The
    count of what was collapsed is returned rather than dropped, so a genuinely
    distinct role cannot vanish silently.

    @return [Array(Array<Hash>, Integer)] (kept, collapsed)
    """
    best = {}
    order = []
    for r in rows:
        company = (r.get("company") or "").lower()
        title = _normalised_title(r.get("title"))
        # A board's own requisition id groups location variants of one job and is
        # the better key wherever the adapter captured it.
        req = r.get("internal_job_id")
        if req:
            key = ("req", company, str(req))
        elif company or title:
            key = (company, title)
        else:
            # Nothing to compare on is not a duplicate; key on identity instead.
            key = ("id", r.get("id"))
        if key not in best:
            best[key] = r
            order.append(key)
        else:
            # Keep every location the collapsed instances named, so a genuinely
            # distinct office is visible rather than silently dropped.
            seen = best[key].setdefault("also_in", [])
            for other in (r.get("location"), *(r.get("also_in") or [])):
                if other and other != best[key].get("location") and other not in seen:
                    seen.append(other)
            if r.get("total", 0) > best[key].get("total", 0):
                r["also_in"] = seen
                best[key] = r
    return [best[k] for k in order], len(rows) - len(best)


# What he is aiming at. Overridable in profile.toml as search.target_shapes;
# fde is included because forward-deployed work is arguably on target for him,
# and that judgment is his rather than the tool's.
DEFAULT_TARGET_SHAPES = ("backend", "fullstack", "platform", "fde", "generic")


def off_target(role_shape, targets):
    """Whether a posting is a kind of role he is not aiming at.

    Reported, never excluded. Whether fde counts as on-target is his call, and a
    filter that silently drops a whole category is how a tool starts deciding for
    someone.

    @return [Boolean]
    """
    return bool(role_shape) and role_shape not in targets


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
    # Dedupe BEFORE the cap, or duplicates spend slots a distinct role could use.
    above, _ = dedupe(above)
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
