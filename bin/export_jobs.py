"""Export scored, recently-seen jobs to JSON for the jobboard front end.

Read-only against jobhunt.db. Stdlib only, per the runtime promise in README.md.
"""
import json
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobhunt.db"

QUERY = """
select j.id, j.company, j.title, j.location, j.remote, j.url,
       j.posted_at, j.last_seen, s.total
from jobs j
join scores s on s.job_id = j.id
where j.last_seen >= date('now', '-14 day')
  and s.breakdown not like '%disqualified%'
order by s.total desc
limit 500
"""


def main(out: Path) -> int:
    """@param out [Path] file to write
    @return [int] exit status"""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(QUERY)]
    con.close()
    out.write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} jobs -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("jobs.json")))
