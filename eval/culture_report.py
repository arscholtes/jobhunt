"""Readable per-company culture report — why each score is what it is.

The point of the report is not the number, it is the line under the number. A
culture score you cannot argue with is a culture score you cannot fix.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from jobhunt import cadence, culture, store
from jobhunt import profile as profile_mod


def main():
    prof = profile_mod.load()
    con = store.connect()
    companies = [r["company"] for r in
                 con.execute("SELECT DISTINCT company FROM jobs ORDER BY company")]

    results = []
    for comp in companies:
        rows = con.execute("SELECT * FROM jobs WHERE company = ?", (comp,)).fetchall()
        if len(rows) < 3:
            continue
        # Cadence is the one term the corpus cannot answer, so it is fetched —
        # cached for a week, and left unknown rather than zeroed when nothing replies.
        cad = store.get_cadence(con, comp)
        if cad is None:
            cad = cadence.for_company(comp, org_overrides=prof.get("github_orgs"),
                                      feeds=prof.get("feeds"))
            store.save_cadence(con, comp, cad)
        ships = (cad["score"], cad["why"]) if cad["score"] is not None else None
        a = culture.assess(rows, prof, ships_often=ships)
        a["company"] = comp
        results.append(a)
    results.sort(key=lambda a: -(a["score"] or 0))

    out = ["# Culture — corpus evidence\n",
           "Derived from postings already in sqlite, plus one cached weekly lookup "
           "per company for shipping cadence — the only term a job posting cannot answer.",
           "A term the corpus cannot speak to scores `unknown` and is excluded from",
           "the denominator, so silence never reads as a bad result.\n",
           "| company | culture | covered | postings | boilerplate |",
           "|---|---:|---:|---:|---:|"]
    for a in results:
        out.append(f"| {a['company']} | **{a['score']}** | {a['covered']}/{a['total_weight']} pts "
                   f"| {a['postings']} | {a['boilerplate_chars']:,} chars |")

    out.append("\n---\n\n## Why each score is what it is\n")
    for a in results:
        out.append(f"### {a['company']} — {a['score']}")
        out.append(f"*{a['postings']} postings · "
                   f"scored on {a['covered']} of {a['total_weight']} weighted points*\n")
        for t in a["terms"]:
            if t["score"] is None:
                out.append(f"- `{t['term']}` (w{t['weight']}) — **unknown** · {t['why']}")
            else:
                bar = "█" * round(t["score"] * 10) + "·" * (10 - round(t["score"] * 10))
                out.append(f"- `{t['term']}` (w{t['weight']}) `{bar}` **{t['score']:.2f}** · {t['why']}")
        if a["boilerplate_chars"]:
            out.append(f"- ⚠️ **{a['boilerplate_chars']:,} chars of identical boilerplate** on every "
                       f"posting — inherited by every role, inflating stack matches company-wide")
        out.append("")

    path = pathlib.Path("eval/out/culture.md")
    path.write_text("\n".join(out))
    print(f"wrote {path} — {len(results)} companies")


if __name__ == "__main__":
    main()
