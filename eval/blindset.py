"""Blind evaluation set for the scorer.

A ranking can only be argued with if a human can judge a posting WITHOUT knowing
who wrote it. Brand does most of the work otherwise: a mediocre posting from a
company you admire reads better than it is, and the scorer's mistakes hide behind
the logo.

So: strip company identity from real postings, stratify across the score range,
and emit numbered cards carrying no score and no name. The answer key is written
to a separate file that the rater must not open first.

Stratification is the point. Sampling only the top of the ranking tells you
nothing about what the model wrongly buried or wrongly promoted, which is exactly
where a scoring bug lives.
"""
import argparse
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import store  # noqa: E402

# Bands to sample from, and how many of each. Deliberately includes disqualified
# postings: an exclusion rule that is too aggressive is invisible in a shortlist.
BANDS = [
    ("top",   85, 101, 3),
    ("upper", 70,  85, 2),
    ("mid",   55,  70, 2),
    ("low",   40,  55, 1),
    ("dq",    -2,   0, 2),
]

URL = re.compile(r"https?://\S+")


def _aliases(company):
    """Surface forms of a company slug likely to appear in its own prose."""
    base = company.strip()
    forms = {base, base.replace("-", " "), base.replace("-", ""), base.replace(".", "")}
    return sorted({f for f in forms if len(f) >= 3}, key=len, reverse=True)


def scrub(text, company, codename):
    """Replace every surface form of the company, and any URL, with placeholders."""
    out = URL.sub("[link removed]", text or "")
    for alias in _aliases(company):
        out = re.sub(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
                     codename, out, flags=re.I)
    return out


def sample(con, seed, per_band=None):
    rng = random.Random(seed)
    picked = []
    for name, lo, hi, n in BANDS:
        rows = con.execute(
            """SELECT j.id, j.company, j.title, j.location, j.remote, j.url,
                      j.description, s.total, s.breakdown
               FROM jobs j JOIN scores s ON s.job_id = j.id
               WHERE s.total >= ? AND s.total < ?""",
            (lo, hi),
        ).fetchall()
        want = per_band if per_band is not None else n
        picked += rng.sample(rows, min(want, len(rows)))
    rng.shuffle(picked)
    return picked


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7, help="deterministic sample")
    ap.add_argument("--chars", type=int, default=2200, help="description budget per card")
    ap.add_argument("--out", default="eval/out", help="directory for cards + key")
    args = ap.parse_args()

    con = store.connect()
    rows = sample(con, args.seed)

    codes, cards, key = {}, [], []
    for i, r in enumerate(rows, 1):
        comp = r["company"]
        if comp not in codes:
            codes[comp] = f"Company {chr(64 + len(codes) + 1)}"
        code = codes[comp]

        desc = scrub(r["description"] or "", comp, code)
        desc = re.sub(r"\n{3,}", "\n\n", desc).strip()
        if len(desc) > args.chars:
            desc = desc[: args.chars].rsplit(" ", 1)[0] + " …[truncated]"

        where = "remote" if r["remote"] else (r["location"] or "not stated")
        cards.append(
            f"### Card {i:02d}\n"
            f"**{scrub(r['title'], comp, code)}** — {code} · {where}\n\n{desc}\n"
        )
        key.append({
            "card": i, "id": r["id"], "codename": code, "company": comp,
            "title": r["title"], "score": r["total"],
            "breakdown": json.loads(r["breakdown"]), "url": r["url"],
        })

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "cards.md").write_text(
        f"# Blind set (seed {args.seed}) — {len(cards)} postings\n\n"
        "No company names, no scores, no links. Rate each on its own terms.\n\n"
        + "\n---\n\n".join(cards)
    )
    (outdir / "key.json").write_text(json.dumps(key, indent=2))

    leaks = [k["card"] for k, c in zip(key, cards) if re.search(
        re.escape(k["company"]), c, re.I)]
    print(f"wrote {outdir/'cards.md'} ({len(cards)} cards, {len(codes)} companies)")
    print(f"wrote {outdir/'key.json'}  — do not open before rating")
    if leaks:
        print(f"WARNING residual name leak on cards: {leaks}")


if __name__ == "__main__":
    main()
