# jobhunt

Finds engineering roles worth applying to, ranks them against a profile you
control, and keeps track of where each application stands.

Stdlib only at runtime — no install step, no dependencies, no API keys.

The promise covers what you need to *run* it. Development tooling (a linter, a
test runner) may bring dependencies; that is a separate contract and the
stdlib-only gate deliberately scopes itself to the runtime package so adding a
linter never reads as breaking a promise about the tool.

```bash
cp profile.example.toml profile.toml   # then edit it
./jobhunt.py fetch                     # poll the boards
./jobhunt.py score                     # rank against your profile
./jobhunt.py list                      # the shortlist
```

## How it works

`profile.toml` is the single source of truth: the titles you want, the ones that
disqualify a posting, your skills and their weights, the things you are trying to
move toward, and the boards to poll. Everything downstream reads from it.

Three job boards publish read-only JSON built for exactly this, and `jobhunt`
reads them directly:

| source | board URL | adapter |
|---|---|---|
| `greenhouse` | `boards.greenhouse.io/TOKEN` | `jobhunt/sources/greenhouse.py` |
| `lever` | `jobs.lever.co/TOKEN` | `jobhunt/sources/lever.py` |
| `ashby` | `jobs.ashbyhq.com/TOKEN` | `jobhunt/sources/ashby.py` |

Add a company by dropping its slug into `[[boards]]`.

## Why the score is a keyword model

Scoring is a transparent weighted keyword match, not embeddings and not a
language model call. The point is that a ranking has to be **arguable**: every
point traces back to a term in the posting, so a bad result is a line you can fix
in `profile.toml` rather than a black box you have to trust.

```
score 74.4  {"title": 30, "skills": 23.4,
             "skills_matched": ["event-driven","python","rails","sql"],
             "interests": 6.0, "location": 15}
```

Postings matching a dealbreaker or an excluded title score `-1` and are dropped
rather than ranked low, so they never crowd the shortlist.

## Tracking

```bash
./jobhunt.py show <job-id>                        # full posting + score breakdown
./jobhunt.py status <job-id> interested --note ".."
```

Statuses: `interested`, `drafted`, `sent`, `rejected`, `closed`.

## What this tool does not do

**It never contacts an employer.** There is no send path in the codebase. Drafting
an application and sending it are separate, deliberate steps a human takes.

## Not built yet

- **Culture research** — scoring a company against `[culture]` needs sources a
  posting cannot supply. Design pending.
- **Resume tailoring** — blocked on a canonical resume to tailor *from*.
- **Application drafting** — depends on the two above.

## Layout

```
jobhunt.py              entry point
jobhunt/
  cli.py                commands
  profile.py            loads and validates profile.toml
  score.py              the fit model
  store.py              sqlite schema + persistence
  sources/              one adapter per job board
profile.example.toml    documented profile template
data/jobhunt.db         local state (gitignored)
```
