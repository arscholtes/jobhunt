"""Command line entry point.

    jobhunt fetch                 poll every board in profile.toml
    jobhunt score                 (re)score everything stored
    jobhunt list [--all] [-n 20]  ranked shortlist
    jobhunt requirements [-n 30]  what the top postings actually ask for
    jobhunt show <job-id>         one posting in full
    jobhunt gate <job-id>         which resume variant it gets, and why
    jobhunt resume <job-id>       render that variant
    jobhunt brief <job-id>        what to match, what you don't, and where to apply
    jobhunt digest [--dry-run]    the daily shortlist; the scheduled job calls this
    jobhunt status <job-id> <s>   interested | drafted | sent | rejected | closed

Nothing in this tool contacts an employer. Drafting and sending are separate,
deliberate steps a human takes.
"""
import argparse
import json
import pathlib
import sys
import textwrap

from . import culture, digest, export, gate, notify, resume, store, tailor
from . import profile as profile_mod
from . import requirements as req_mod
from . import score as score_mod
from . import signals as signals_mod
from .sources import fetch as fetch_source
from .sources._http import FetchError


def _load_profile(args):
    try:
        return profile_mod.load(getattr(args, "profile", None))
    except profile_mod.ProfileError as e:
        sys.exit(f"error: {e}")


def apply_board_name(rows, board):
    """Use the board's display name as the company, where one is given.

    A token is an address: Podium's Greenhouse board answers to "podium81", and
    without this every posting from it is filed under a company of that name —
    which is what the digest shows and what boilerplate and culture scoring group
    on. The posting id is deliberately untouched, since it encodes the address and
    rewriting it would make every known posting look new.

    @param rows [Array<Hash>] postings as the adapter returned them
    @param board [Hash] the [[boards]] entry
    @return [Array<Hash>]
    """
    name = (board.get("name") or "").strip()
    if not name:
        return rows
    for r in rows:
        r["company"] = name
    return rows


def cmd_fetch(args):
    prof = _load_profile(args)
    boards = prof["boards"]
    if not boards:
        sys.exit("error: no [[boards]] in profile.toml — add at least one.")
    con = store.connect()
    total_new = total_seen = 0
    for b in boards:
        label = f"{b['source']}/{b['token']}"
        try:
            rows = apply_board_name(fetch_source(b["source"], b["token"]), b)
        except (FetchError, ValueError) as e:
            print(f"  {label:28} skipped — {e}")
            continue
        new, seen = store.upsert_jobs(con, rows)
        total_new += new
        total_seen += seen
        print(f"  {label:28} {len(rows):4} listed   {new:4} new")
    print(f"\n{total_new} new, {total_seen} already known.")
    if total_new:
        print("Run `jobhunt score` to rank them.")


def cmd_score(args):
    prof = _load_profile(args)
    con = store.connect()
    jobs = con.execute("SELECT * FROM jobs").fetchall()

    # Per-company boilerplate is computed once across that company's whole set of postings,
    # then stripped from each posting before it is scored. Without this a company
    # that repeats its stack on every posting gives all of them a perfect skills
    # score, ranking its field roles above its engineering ones.
    by_company = {}
    for j in jobs:
        by_company.setdefault(j["company"], []).append(j)
    boilerplate = {c: (culture.boilerplate(rows), culture.boilerplate_suffix(rows))
                   for c, rows in by_company.items()}

    kept = dropped = 0
    stripped_companies = sum(1 for pre, suf in boilerplate.values() if pre or suf)
    for j in jobs:
        job = dict(j)
        reason = score_mod.dealbreaker(job, prof)
        if reason:
            store.save_score(con, job["id"], -1, {"disqualified": reason})
            dropped += 1
            continue
        pre, suf = boilerplate.get(job["company"], ("", ""))
        total, breakdown = score_mod.score(job, prof, boilerplate=pre, suffix=suf)
        sig = signals_mod.extract(job)
        delta, why = signals_mod.bonus(sig, prof)
        if delta:
            total = max(0.0, round(total + delta, 1))
            breakdown["signals"] = why
        breakdown["interview"] = sig["interview"]
        breakdown["ai_stance"] = sig["ai_stance"]
        breakdown["friction"] = sig["friction"]
        store.save_score(con, job["id"], total, breakdown)
        kept += 1
    print(f"scored {kept}, disqualified {dropped}"
          + (f", boilerplate stripped for {stripped_companies} compan"
             f"{'y' if stripped_companies == 1 else 'ies'}" if stripped_companies else ""))

    # The sheet is regenerated HERE rather than only in the daily digest, because
    # scoring is where the data changes. Hooked to the digest alone it sat up to
    # 24 hours behind a moving database while looking authoritative, which is the
    # stale-derived-artifact failure this codebase has now hit several times.
    # The hourly scan scores, so it gets a fresh sheet for free.
    bar = digest.percentile_bar([r[0] for r in con.execute("SELECT total FROM scores")])
    sheet = _write_sheet(con, bar)
    if sheet:
        print(f"sheet refreshed: {sheet.name}")


def cmd_list(args):
    prof = _load_profile(args)
    floor = -1 if args.all else prof["search"]["min_score"]
    con = store.connect()
    rows = con.execute(
        """SELECT j.id, j.company, j.title, j.location, j.remote, j.description, s.total,
                  COALESCE(a.status,'') AS status
           FROM jobs j JOIN scores s ON s.job_id = j.id
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE s.total >= ? ORDER BY s.total DESC LIMIT ?""",
        (floor, args.n),
    ).fetchall()
    if not rows:
        print("Nothing above the score floor. `jobhunt list --all` shows everything.")
        return
    for r in rows:
        loc = r["location"] or "—"
        if r["remote"]:
            loc = "remote" if loc == "—" else f"remote · {loc}"
        flag = f"  [{r['status']}]" if r["status"] else ""
        print(f"{r['total']:5.1f}  {r['company'][:16]:16}  "
              f"{r['title'][:46]:46}  {loc[:22]:22}{flag}")
        # Eligibility is shown, never applied: nothing here removes a posting.
        labels = gate.flag_labels(dict(r))
        print(f"       {r['id']}" + (f"   ⚑ {labels}" if labels else ""))


def cmd_requirements(args):
    prof = _load_profile(args)
    con = store.connect()
    rows = con.execute(
        """SELECT j.* FROM jobs j JOIN scores s ON s.job_id = j.id
           WHERE s.total >= 0 ORDER BY s.total DESC LIMIT ?""", (args.n,)).fetchall()

    # The same boilerplate that distorts scoring would distort a demand count: a
    # stack blurb repeated on every advert is one company's marketing, not the market.
    by_company = {}
    for r in rows:
        by_company.setdefault(r["company"], []).append(r)
    all_rows = con.execute("SELECT * FROM jobs").fetchall()
    by_company = {}
    for r in all_rows:
        by_company.setdefault(r["company"], []).append(r)
    boiler = {c: (culture.boilerplate(by_company.get(c, [])),
                  culture.boilerplate_suffix(by_company.get(c, [])))
              for c in by_company}

    print(req_mod.render(req_mod.summarise([dict(r) for r in rows], prof, boilerplate=boiler)))


def sheet_reference(path):
    """How to reach the spreadsheet, in both places he reads the digest.

    No single URL works in both. A file:// link is live in Mail on the desktop and
    inert in Mail on iOS, so shipping only that ships something that silently does
    nothing on the device he actually reads this on. The desktop gets the link and
    the phone gets the location in words.

    @param path [pathlib.Path]
    @return [Array<String>]
    """
    lines = [f"spreadsheet   file://{path}"]
    try:
        rel = path.relative_to(export.ICLOUD.parent)
        lines.append(f"              on the phone: iCloud Drive > {' > '.join(rel.parts)}")
    except ValueError:
        lines.append(f"              on the phone: {path.name}, in iCloud Drive")
    return lines


def _write_sheet(con, bar):
    """Regenerate the browsable shortlist. The whole thing, not today's delta.

    @return [pathlib.Path, nil] nil when it could not be written
    """
    rows = con.execute(
        """SELECT j.*, s.total, COALESCE(a.status, '') AS status
           FROM jobs j JOIN scores s ON s.job_id = j.id
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE s.total >= ? ORDER BY s.total DESC""", (bar,)).fetchall()
    try:
        return export.write([dict(r) for r in rows])
    except OSError as e:
        # iCloud not mounted is not a reason to lose the digest.
        print(f"  sheet not written: {e}")
        return None


def _print_picked(picked, targets):
    """List the day's postings, marking the ones outside the target shapes.

    Marked, never removed. Whether a frontend or ML role is worth his time is his
    call; the tool's job is only to stop one passing unnoticed.
    """
    shapes = []
    for r in picked:
        shape = gate.decide(r).get("role_shape") or "?"
        shapes.append(shape)
        adrift = digest.off_target(shape, targets)
        note = gate.flag_labels(r)
        print(f"  {'!' if adrift else '·'} {r['total']:5.1f}  {shape:<9} "
              f"{r['company']:<12} {r['title'][:44]}" + (f"   ⚑ {note}" if note else ""))
        if r.get("also_in"):
            print(f"          also listed in {', '.join(r['also_in'][:3])}")
    summary = digest.summarise_off_target(shapes, targets)
    if summary["count"]:
        print(f"\n  ! {summary['count']} of {len(picked)} are shapes you are not "
              f"targeting: {', '.join(summary['shapes'])}")


def cmd_digest(args):
    """The daily shortlist, and the one thing a scheduled job calls.

    The bar is a percentile of the scored postings rather than a constant, because a constant
    was silently invalidated once already: stripping boilerplate lowered every
    score and a fixed bar of 60 began withholding good postings, the best of them
    missing by 0.2.

    Nothing is marked notified until the send has returned. A refused connection
    must delay a posting, never drop it — the digest is a delta defined by that
    table, not by a time window.
    """
    con = store.connect()
    totals = [r[0] for r in con.execute("SELECT total FROM scores")]
    bar = digest.percentile_bar(totals)
    rows = [dict(r) for r in notify.unsent(con, min_score=bar, limit=500)]
    picked, held = digest.select_with_overflow(rows, bar, limit=args.limit)

    print(f"bar {bar:.1f} (post analysis {int(digest.DEFAULT_PERCENTILE * 100)}th percentile)")

    # Written every run and regenerated whole, so it cannot drift from the
    # database. It carries the entire shortlist rather than the unsent delta —
    # it is for browsing, and a sheet holding only this morning's new postings
    # would not be that.
    sheet = _write_sheet(con, bar)

    if not picked:
        print("nothing new above the bar — sending nothing")
        if sheet:
            for line in sheet_reference(sheet):
                print(line)
        return

    prof = _load_profile(args) if getattr(args, "profile", None) is not None else None
    targets = set((prof or {}).get("search", {}).get("target_shapes")
                  or digest.DEFAULT_TARGET_SHAPES)

    verb = "would send" if args.dry_run else "sending"
    held_note = f", {held} held for tomorrow" if held else ""
    print(f"{verb} {len(picked)} posting(s){held_note}")
    _print_picked(picked, targets)

    if sheet:
        print()
        for line in sheet_reference(sheet):
            print(line)

    if args.dry_run:
        print("\ndry run — nothing sent, nothing marked notified")
        return

    try:
        notify.send(picked)
    except Exception as e:
        # Deliberately not marked: the same postings ride tomorrow.
        sys.exit(f"send failed, nothing marked: {type(e).__name__}: {e}")
    store.mark_notified(con, [r["id"] for r in picked])
    print(f"sent, and marked {len(picked)} notified")


def cmd_brief(args):
    con = store.connect()
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (args.job_id,)).fetchone()
    if not row:
        sys.exit(f"no posting with id {args.job_id}")
    job = dict(row)
    try:
        facts = resume.load(getattr(args, "resume", None))
    except resume.ResumeError as e:
        sys.exit(str(e))
    print(tailor.brief(job, facts, gate.decide(job)))


def cmd_show(args):
    con = store.connect()
    r = con.execute(
        """SELECT j.*, s.total, s.breakdown, COALESCE(a.status,'') AS status, a.notes
           FROM jobs j LEFT JOIN scores s ON s.job_id = j.id
           LEFT JOIN applications a ON a.job_id = j.id WHERE j.id = ?""",
        (args.job_id,),
    ).fetchone()
    if not r:
        sys.exit(f"error: no job with id {args.job_id!r}")
    print(f"{r['title']}\n{r['company']}  ·  {r['location'] or '—'}\n{r['url']}\n")
    if r["total"] is not None:
        print(f"score {r['total']}   {json.dumps(json.loads(r['breakdown']))}\n")
    if r["status"]:
        print(f"status {r['status']}" + (f" — {r['notes']}" if r["notes"] else "") + "\n")
    print(textwrap.fill(r["description"] or "(no description)", 88)[:4000])


def cmd_status(args):
    con = store.connect()
    if not con.execute("SELECT 1 FROM jobs WHERE id = ?", (args.job_id,)).fetchone():
        sys.exit(f"error: no job with id {args.job_id!r}")
    try:
        store.set_status(con, args.job_id, args.status, args.note)
    except ValueError as e:
        sys.exit(f"error: {e}")
    print(f"{args.job_id} → {args.status}")


def _job(con, job_id):
    r = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not r:
        sys.exit(f"error: no job with id {job_id!r}")
    return r


def cmd_gate(args):
    """Explain which resume a posting gets, and why."""
    r = _job(store.connect(), args.job_id)
    d = gate.decide(r)
    print(f"{r['title']}\n{r['company']}  ·  {r['location'] or '—'}\n")
    print(f"variant  {d['variant']}")
    for reason in d["reasons"]:
        print(f"         {reason}")
    if d["flags"]:
        print()
        for name, evidence in d["flags"]:
            print(f"FLAG     {name}: {evidence!r}")


def cmd_resume(args):
    """Render the resume this posting should get."""
    r = _job(store.connect(), args.job_id)
    d = gate.decide(r)
    try:
        text = resume.generate(d["shape"], d["domain"])
    except resume.ResumeError as e:
        sys.exit(f"error: {e}")
    if args.out:
        pathlib.Path(args.out).write_text(text)
        print(f"{d['variant']} → {args.out}")
    else:
        print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jobhunt", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", help="path to profile.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fetch", help="poll every board in the profile").set_defaults(fn=cmd_fetch)
    sub.add_parser("score", help="rescore every stored posting").set_defaults(fn=cmd_score)

    p = sub.add_parser("list", help="ranked shortlist")
    p.add_argument("-n", type=int, default=25)
    p.add_argument("--all", action="store_true", help="ignore the score floor")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("requirements", help="what the top postings actually ask for")
    p.add_argument("-n", type=int, default=30, help="how many of the top postings to read")
    p.set_defaults(fn=cmd_requirements)

    p = sub.add_parser("digest", help="the daily shortlist of what is new")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would be sent, send nothing, mark nothing")
    p.add_argument("--limit", type=int, default=digest.DEFAULT_LIMIT)
    p.set_defaults(fn=cmd_digest)

    p = sub.add_parser("brief", help="a page to write an application from")
    p.add_argument("job_id")
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("show", help="one posting in full")
    p.add_argument("job_id")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("gate", help="which resume variant a posting gets, and why")
    p.add_argument("job_id")
    p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("resume", help="render the resume variant for a posting")
    p.add_argument("job_id")
    p.add_argument("-o", "--out", help="write to a file instead of stdout")
    p.set_defaults(fn=cmd_resume)

    p = sub.add_parser("status", help="record where an application stands")
    p.add_argument("job_id")
    p.add_argument("status", choices=store.STATUSES)
    p.add_argument("--note")
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
