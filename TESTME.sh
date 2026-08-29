#!/bin/bash
# Drive every change on this branch by hand before it goes anywhere.
# Run from the repo root:  ./TESTME.sh
#
# Read-only against the boards and your mail. The only thing it writes is
# eval/out/, which is gitignored.
set -uo pipefail
PY=/opt/homebrew/bin/python3
cd "$(dirname "$0")" || exit 1

hr(){ printf '\n\033[1m── %s\033[0m\n' "$1"; }

hr "1. The suite (stdlib unittest, no install step)"
$PY -m unittest discover -s tests 2>&1 | tail -4

hr "2. The gate — must say PASS before anything goes up"
~/.claude/skills/qa-gate/qa-gate.sh . 2>&1 | tail -9

hr "3. Two new boards registered (want 5 adapters)"
$PY -c "from jobhunt.sources import ADAPTERS; print('  ', sorted(ADAPTERS))"

hr "4. Title exclusions catch suffixes ('intern' -> 'Internship')"
$PY -c "
from jobhunt import score, profile
p = profile.load('profile.toml')
for t in ['Software Engineer Internship','Software Engineer, New Grad (Dec 2026)','Senior Software Engineer']:
    print(f'  {t:40} -> {score.dealbreaker({\"title\":t,\"description\":\"\"}, p)}')"

hr "5. Your dealbreakers can actually fire (punctuation can silently kill one)"
$PY -c "
from jobhunt import score, profile
p = profile.load('profile.toml')
for d in p.get('dealbreakers', []):
    pat = d['pattern']
    job = {'title':'Software Engineer','description':'We require ' + pat + ' for this role.'}
    print(f'  {\"FIRES\" if score.dealbreaker(job,p) else \"DEAD \"}  {pat!r}')"

hr "6. Digest is a delta from the notified table, not a time window"
$PY -c "
from jobhunt import notify, store
con = store.connect()
n = con.execute('SELECT count(*) FROM notified').fetchone()[0]
print(f'   {n} already recorded as emailed')
print(f'   {len(notify.unsent(con, min_score=60))} unsent above 60 (would send next run)')"

hr "7. Shortlist — eligibility flags now ride each row (they inform, never filter)"
$PY jobhunt.py list -n 8

hr "8. Boilerplate stripping: does a company's repeated stack still inflate its non-eng roles?"
$PY -c "
from jobhunt import store
con = store.connect()
rows = con.execute('''SELECT j.company, j.title, s.total FROM jobs j JOIN scores s ON s.job_id=j.id
                      WHERE j.company='replit' AND s.total > 0 ORDER BY s.total DESC LIMIT 8''')
for r in rows: print(f'  {r[\"total\"]:6.1f}  {r[\"title\"][:58]}')
print('  ^ engineering roles should sit above marketing/brand ones')"

hr "9. Resume gate explains its choice, and renders"
JID=$($PY -c "
from jobhunt import store
print(store.connect().execute('SELECT id FROM jobs LIMIT 1').fetchone()['id'])")
$PY jobhunt.py gate "$JID"
echo "  --- rendered (first 8 lines) ---"
$PY jobhunt.py resume "$JID" | head -8

hr "10. Culture report — corpus-derived, deliberately NOT wired into scoring"
$PY eval/culture_report.py 2>&1 | tail -3

printf '\n\033[1mNot covered here:\033[0m a real SMTP send (needs ~/.jobhunt-mail.toml) and\n'
printf '`jobhunt fetch`, which hits the live boards. Run those by hand if you want them.\n'
printf 'Known and deliberate: a region-locked posting still scores full remote points.\n'
printf 'It is flagged, not filtered — see commit 8d1f02c.\n'
