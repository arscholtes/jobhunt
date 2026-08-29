"""SQLite persistence. One file, no migrations framework, no ORM."""
import datetime
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "jobhunt.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id            TEXT PRIMARY KEY,      -- source:company:external_id
  source        TEXT NOT NULL,
  company       TEXT NOT NULL,
  title         TEXT NOT NULL,
  location      TEXT,
  remote        INTEGER,               -- 1 / 0 / NULL when unknown
  url           TEXT NOT NULL,
  description   TEXT,
  posted_at     TEXT,
  first_seen    TEXT NOT NULL,
  last_seen     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
  job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  total      REAL NOT NULL,
  breakdown  TEXT NOT NULL,            -- json
  scored_at  TEXT NOT NULL
);

-- What has actually been emailed. The digest is a delta, and a time window is
-- not a safe proxy for one: a missed run, a sleeping laptop, or unconfigured
-- mail would drop a qualifying posting permanently. A row here is written only
-- after the send succeeds, so an unsent posting is simply retried next hour.
CREATE TABLE IF NOT EXISTS notified (
  job_id      TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  notified_at TEXT NOT NULL
);

-- Application state is deliberately explicit. Nothing moves to 'sent' without
-- a human doing it; see jobhunt.cli.
CREATE TABLE IF NOT EXISTS applications (
  job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  status     TEXT NOT NULL,            -- interested | drafted | sent | rejected | closed
  notes      TEXT,
  updated_at TEXT NOT NULL
);

-- Shipping cadence comes from someone else's API, so it is cached rather than
-- refetched per report. A stale answer is fine; hammering an unauthenticated
-- endpoint until it rate-limits is not.
CREATE TABLE IF NOT EXISTS cadence (
  company    TEXT PRIMARY KEY,
  data       TEXT NOT NULL,            -- json
  fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_seen    ON jobs(last_seen);
CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total);
"""

STATUSES = ("interested", "drafted", "sent", "rejected", "closed")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def upsert_jobs(con, jobs):
    """Insert new postings, refresh last_seen on ones already known.

    Returns (new_count, seen_count).
    """
    new = seen = 0
    ts = now()
    for j in jobs:
        cur = con.execute("SELECT 1 FROM jobs WHERE id = ?", (j["id"],))
        if cur.fetchone():
            con.execute("UPDATE jobs SET last_seen = ? WHERE id = ?", (ts, j["id"]))
            seen += 1
        else:
            con.execute(
                """INSERT INTO jobs (id, source, company, title, location, remote, url,
                                     description, posted_at, first_seen, last_seen)
                   VALUES (:id, :source, :company, :title, :location, :remote, :url,
                           :description, :posted_at, :ts, :ts)""",
                {**j, "ts": ts},
            )
            new += 1
    con.commit()
    return new, seen


def save_score(con, job_id, total, breakdown):
    con.execute(
        "INSERT OR REPLACE INTO scores (job_id, total, breakdown, scored_at) VALUES (?,?,?,?)",
        (job_id, total, json.dumps(breakdown), now()),
    )
    con.commit()


def mark_notified(con, job_ids):
    """Record that these postings have been emailed.

    @param job_ids [Iterable<str>] ids that were included in a successful send
    @return [int] rows written
    """
    ts = now()
    rows = [(jid, ts) for jid in job_ids]
    con.executemany(
        "INSERT OR IGNORE INTO notified (job_id, notified_at) VALUES (?,?)", rows
    )
    con.commit()
    return len(rows)


def save_cadence(con, company, data):
    """@param data [Hash] whatever cadence.for_company resolved; stored as json"""
    con.execute("INSERT OR REPLACE INTO cadence (company, data, fetched_at) VALUES (?,?,?)",
                (company, json.dumps(data), now()))
    con.commit()


def get_cadence(con, company, max_age_days=7):
    """@return [Hash, nil] the cached answer, or nil when absent or too old to trust."""
    row = con.execute("SELECT data, fetched_at FROM cadence WHERE company = ?", (company,)).fetchone()
    if not row:
        return None
    try:
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(row["fetched_at"])
    except (ValueError, TypeError):
        return None
    if age.days > max_age_days:
        return None
    try:
        return json.loads(row["data"])
    except (json.JSONDecodeError, ValueError):
        return None


def set_status(con, job_id, status, notes=None):
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {', '.join(STATUSES)}")
    con.execute(
        """INSERT INTO applications (job_id, status, notes, updated_at) VALUES (?,?,?,?)
           ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,
                                             notes=COALESCE(excluded.notes, applications.notes),
                                             updated_at=excluded.updated_at""",
        (job_id, status, notes, now()),
    )
    con.commit()
