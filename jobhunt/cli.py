"""Command line entry point.

    jobhunt fetch                 poll every board in profile.toml
    jobhunt score                 (re)score everything stored
    jobhunt list [--all] [-n 20]  ranked shortlist
    jobhunt show <job-id>         one posting in full
    jobhunt gate <job-id>         which resume variant it gets, and why
    jobhunt resume <job-id>       render that variant
    jobhunt status <job-id> <s>   interested | drafted | sent | rejected | closed

Nothing in this tool contacts an employer. Drafting and sending are separate,
deliberate steps a human takes.
"""
import argparse, json, pathlib, sys, textwrap

from . import signals as signals_mod, store, profile as profile_mod, score as score_mod
from . import gate, resume, culture
from .sources import fetch as fetch_source
from .sources._http import FetchError


def _load_profile(args):
    try:
        return profile_mod.load(getattr(args, "profile", None))
    except profile_mod.ProfileError as e:
        sys.exit(f"error: {e}")


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
            rows = fetch_source(b["source"], b["token"])
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

    # Per-company boilerplate is computed once across that company's whole corpus,
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
        print(f"{r['total']:5.1f}  {r['company'][:16]:16}  {r['title'][:46]:46}  {loc[:22]:22}{flag}")
        # Eligibility is shown, never applied: nothing here removes a posting.
        labels = gate.flag_labels(dict(r))
        print(f"       {r['id']}" + (f"   ⚑ {labels}" if labels else ""))


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
    d = gate.decide({"title": r["title"], "description": r["description"]})
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
    d = gate.decide({"title": r["title"], "description": r["description"]})
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
