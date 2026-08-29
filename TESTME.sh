#!/bin/bash
# Drive every change on the jobhunt-landing branch. Read-only except where noted.
# Run from ~/Developer/jobhunt on branch jobhunt-landing.  Delete this file after.
set -uo pipefail
PY=/opt/homebrew/bin/python3
cd "$(dirname "$0")" || exit 1

hr(){ printf '\n\033[1m── %s\033[0m\n' "$1"; }

hr "1. Two new boards registered (want 5 adapters)"
$PY -c "from jobhunt.sources import ADAPTERS; print('  ', sorted(ADAPTERS))"

hr "2. Title exclusions now catch suffixes ('intern' -> 'Internship')"
$PY -c "
from jobhunt import score, profile
p = profile.load('profile.toml')
for t in ['Software Engineer Internship','Senior Software Engineer']:
    print(f'  {t:38} -> {score.dealbreaker({\"title\":t,\"description\":\"\"}, p)}')"

hr "3. Digest is a delta defined by the notified table, not a time window"
$PY -c "
from jobhunt import notify, store
con = store.connect()
n = con.execute('SELECT count(*) FROM notified').fetchone()[0]
print(f'   {n} posting(s) already recorded as emailed')
print(f'   {len(notify.unsent(con, min_score=60))} unsent above 60 (would be sent next run)')"

hr "4. Resume gate explains its choice (no score change, display only)"
JID=$($PY -c "
from jobhunt import store
r=store.connect().execute('SELECT id FROM jobs LIMIT 1').fetchone(); print(r['id'])")
$PY jobhunt.py gate "$JID"

hr "5. Rendered variant for that same posting (first 12 lines)"
$PY jobhunt.py resume "$JID" | head -12

hr "6. Culture report — corpus-derived, NOT wired into scoring"
$PY eval/culture_report.py 2>&1 | tail -12

hr "7. Blind eval set (writes to eval/out/, which is gitignored)"
$PY eval/blindset.py --help 2>&1 | head -8

hr "8. Shortlist still renders"
$PY jobhunt.py list -n 5

printf '\n\033[1mNOT exercised here:\033[0m real SMTP send (needs ~/.jobhunt-mail.toml)\n'
printf 'and `jobhunt fetch`, which hits the live boards. Run those by hand if you want them.\n'
