"""The shortlist as a spreadsheet, for reading somewhere other than an email.

CSV rather than a .numbers bundle: Numbers opens it natively, it needs no third
party library, and a person with no tools at all can still read it in ten years.
Driving Numbers over AppleScript would buy formatting and cost reliability.

Written into iCloud Drive so it reaches the phone and iPad without a second
mechanism, and REGENERATED on every run rather than appended — an appended sheet
drifts from the database it claims to describe, and a spreadsheet nobody trusts
is worse than no spreadsheet.
"""
import csv
import pathlib

ICLOUD = pathlib.Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/jobhunt"
DEFAULT_PATH = ICLOUD / "shortlist.csv"

COLUMNS = [
    ("score", lambda r: f"{r['total']:.1f}"),
    ("company", lambda r: r["company"]),
    ("title", lambda r: r["title"]),
    ("where", lambda r: "remote" if r.get("remote") else (r.get("location") or "")),
    ("status", lambda r: r.get("status") or ""),
    ("first seen", lambda r: (r.get("first_seen") or "")[:10]),
    ("apply", lambda r: r.get("url") or ""),
    ("id", lambda r: r.get("id") or ""),
]


def write(rows, path=None):
    """Write the shortlist, best match first.

    @param rows [Iterable<Mapping>] scored postings
    @param path [pathlib.Path] destination; defaults to the iCloud Drive copy
    @return [pathlib.Path] where it was written
    """
    path = pathlib.Path(path) if path else DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: -float(r["total"]))
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([name for name, _ in COLUMNS])
        for r in ordered:
            w.writerow([fn(r) for _, fn in COLUMNS])
    return path
