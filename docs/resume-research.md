# Resume construction — what the evidence actually supports

Research pass, 2026-08-28. Written to inform the resume-variant and gate design.
Every claim is graded by how well it is sourced, because roughly half the search
surface on this topic is SEO content marketing that cites itself in a circle.

**Grading:** `[strong]` primary source or named study with a method.
`[moderate]` named survey, small n, or a vendor with skin in the game.
`[weak]` uniform blog consensus, no underlying measurement. `[unverified]` a
claim worth knowing that nobody has substantiated.

---

## 1. The premise most resume advice is built on is false

**`[strong]` No major ATS auto-rejects a resume on content.**

The "75% of resumes are rejected by the ATS before a human sees them" figure
traces to Preptel, a resume-optimization vendor, circa 2012. Preptel shut down in
August 2013 and never published a study, a dataset, or a method. The number
drifts between 70%, 75%, and 88% depending on who is repeating it — a real
statistic has one value and one source; this one has never had either.

What the platforms actually do:

- **Greenhouse** does not score or rank resumes at all. The only automatic
  rejection is a *knockout question* the employer configured (work authorization,
  location, years of experience). Everything else is read by a human.
- **Lever** does not score resumes. Recruiters work from search results.
- Parsing failure does not remove you from the pile. Greenhouse creates the
  candidate record anyway and the recruiter fills missing fields from the
  attached document. **You lose clean searchability, not your place in the queue.**

Recruiter surveys agree: in Enhancv's 2025 study (n=25) 92% said their systems do
not auto-reject at all; a LinkedIn poll (n=630) put it at 83%, rising to 97% among
experienced recruitment professionals.

The one real, well-sourced screening statistic is different in kind: Harvard
Business School / Accenture, *Hidden Workers: Untapped Talent* (Sept 2021) found
88% of employers say qualified candidates get screened out — **by rigid criteria
recruiters configured**, not by an algorithm judging prose.

### What this changes

Keyword stuffing to "beat the ATS" optimizes a gate that does not exist. Keywords
still matter, but for two *different* reasons, and the difference dictates how you
use them:

1. **Recruiter search.** Greenhouse/Lever recruiters find candidates by querying
   their own database. Terms you do not use are terms you cannot be found by.
   This rewards *presence and correct spelling* of real technologies — once each,
   in a place a parser will read. It does not reward density.
2. **LLM screening** (§3), which reads for meaning, not tokens.

Both reward the same thing: true, specific, plainly-stated terms. Neither rewards
a keyword salad, and a human reading page one is actively repelled by one.

---

## 2. The real mechanical risk is layout, not vocabulary

**`[moderate]` Parsers read a linear text stream; anything that is not linear
gets scrambled or dropped.**

From practitioner testing across 8 ATS systems, plus UnchartedCareer's June 2026
run (48 synthetic resumes, 9 layouts, 3 open-source extractors):

| Construction | Result |
|---|---|
| Two-column layout | Failed in 7 of 8 systems — read left-to-right across both columns, producing scrambled text |
| Content inside tables | Partially extracted or skipped entirely in 5 of 8; Workday's parser fails even a simple two-column skills table |
| Text in headers/footers | Ignored — parsers read the body only |
| Image-based text | Lost name, email and phone **100% of the time** |

The failure mode is quiet. Nothing tells you it happened.

### Construction rules that follow

- Single column. No tables, no text boxes, no sidebars.
- Contact details in the body, never in a header or footer.
- Real selectable text. No graphics carrying information, no icon-only contact rows.
- Standard section headings (`Experience`, `Skills`, `Education`) — parsers key on them.
- Standard date formats, consistently.
- Submit the format the employer asks for; where free to choose, a text-layer PDF
  exported from a text tool is safe. A scanned or image-flattened PDF is the one
  genuinely fatal choice.

These are cheap, and unlike keyword games they defend against a failure that is
real and measured.

---

## 3. The genuinely new thing in 2026 is LLM screening

**`[moderate]` Adoption is real but not universal; the mechanism differs from
keyword matching in a way that changes what to write.**

Roughly 44% of companies report using AI for resume screening, and about
two-thirds of recruiters plan to expand AI pre-screening in 2026. The systems are
LLM-based: they read for context and meaning rather than matching tokens.

Practical consequences:

- **Coherence beats density.** A model reading for "has this person built
  multi-tenant systems" is answered by a bullet describing one, not by the phrase
  appearing four times.
- **Unexplained jargon scores worse than plain description.** The model, like a
  human, rewards a claim it can follow.
- **Specificity is legible to a model.** Named systems, real constraints and
  concrete outcomes read as evidence; "responsible for" reads as filler.

`[strong, cautionary]` A controlled University of Washington study found LLM
resume screeners preferred white-associated names 85% of the time over
Black-associated names. Worth knowing about the systems in the loop. Not
actionable in resume construction, and noted here so the record is honest rather
than reassuring.

---

## 4. Structure and length

**`[weak, but uniform and low-stakes]`**

- **Two pages is fine and often preferred at senior level.** Compressing real
  experience onto one page costs font size and detail without buying anything.
- **Page one must stand alone.** Assume the recruiter screen reads only page one
  and the hiring manager reads page two. Strongest material first, always.
- **A tight summary, 2–3 lines.** It is the one place to state role shape
  explicitly — which is exactly what a keyword model cannot infer (§6).
- **4–6 bullets per role, quantified where a number is honest.** "Reduced X by
  32% in six months by doing Y" outperforms "responsible for X." Where no honest
  number exists, scale and constraint substitute: "across 22 tenants,"
  "on a 15-year-old monolith."

**`[unverified]`** A widely-repeated 2026 claim holds that languages and
frameworks have dropped to third-tier signal while architecture, code-quality
judgment and AI-assisted workflow are the new differentiators. It appears only on
content-marketing sites with no study behind it. Treat as a hypothesis, not a
finding. It is *directionally* consistent with §3 — but do not restructure a
resume around an unsourced claim.

**`[unverified]`** Likewise the advice to list AI tooling: naming Claude Code or
Copilot in a skills list is noise. If AI-assisted workflow is a real differentiator
it has to show up as an *outcome* — something delivered at a pace or scale the
tool made possible — or not at all.

---

## 5. What this means for a multi-resume pipeline

The findings invert the usual design. If no bot is filtering on keywords, then
per-posting keyword tailoring is low-value busywork. What *is* high-value:

1. **Parse-safety** — one construction decision, made once, applied to every variant.
2. **Role-shape match** — a backend posting and a product-engineering posting want
   different first-page evidence. This is a *selection* problem, not a rewriting one.
3. **Domain match** — an AI-infrastructure company and a logistics SaaS reading the
   same "Senior Software Engineer" title want different framing.
4. **Searchable vocabulary** — every true technology named once, correctly.

That argues for a small set of genuinely different base resumes selected by a
deterministic gate, rather than one master resume rewritten per application.

## 6. The measurement that should drive the variant set

Against the live post analysis (1,839 postings; 206 scoring ≥ 45):

| Role shape | Share of shortlist |
|---|---|
| Generic "Software Engineer" | 30.6% |
| Backend | 22.8% |
| Support / forward-deployed / solutions | 14.1% |
| Platform / DX | 9.7% |
| Full-stack | 6.3% |
| Infrastructure / SRE | 5.8% |
| Security | 4.4% |
| Frontend | 2.4% |
| Mobile / product / data | ~4% |

And the domain axis, measured on posting bodies, cuts *across* those titles:

| Domain | Share of shortlist |
|---|---|
| AI / LLM product | 41.3% |
| Ruby / Rails shop | 36.4% |
| Developer tools | 28.6% |
| Multi-tenant SaaS | 4.9% |

Two independent axes. Title alone cannot separate a Senior Software Engineer at an
LLM-infra company from one at a logistics SaaS, and those two want different
first-page emphasis. **The gate therefore needs both dimensions** — role shape
picks the base document, domain adjusts the summary and skill ordering.

This is the same classification the scorer already needs: role-shape blindness is
a known open defect (security and frontend roles score well because the JS/React
weights match, with nothing encoding "backend/platform, not frontend"). One
classifier, two consumers — the gate that picks a resume and the scorer that
ranks the posting.

---

## Sources

- [The "75% of resumes are auto-rejected" myth, traced to its source](https://unchartedcareer.com/blog/the-75-of-resumes-are-auto-rejected-myth-traced-to-its-source)
- [ATS Rejection Myth Debunked: 92% of Recruiters Confirm ATS Do NOT Automatically Reject Resumes — HR.com](https://www.hr.com/en/app/blog/2026/04/ats-rejection-myth-debunked-92-of-recruiters-confi_mntajhyq.html)
- [The ATS Resume Rejection Myth — The Interview Guys](https://blog.theinterviewguys.com/ats-resume-rejection-myth/)
- [Why ATS Tables and Columns Break Your Resume Parsing — Jobscan](https://www.jobscan.co/blog/resume-tables-columns-ats/)
- [ATS Resume Formatting Mistakes to Avoid — Jobscan](https://www.jobscan.co/blog/ats-formatting-mistakes/)
- [I Tested 8 ATS Systems to See How They Actually Parse Resumes](https://quickcv.io/blog/i-tested-8-ats-systems-to-see-how-they-actually-parse-resumes)
- [AI in Hiring Statistics 2026: Adoption, Bias & Trust](https://employerbranding.news/resources/ai-in-hiring-statistics-2026-adoption-bias-trust-and-regulation/)
- [AI Recruiting Statistics 2026 (SHRM & LinkedIn data)](https://copilot.recruitaisuite.com/blog/ai-recruiting-statistics-2026/)
- [One Page vs Two Pages: Engineering Resume Length by Experience Level](https://www.techinterview.org/post/3233474607/engineering-resume-one-page-vs-two/)
- Harvard Business School / Accenture, *Hidden Workers: Untapped Talent* (Sept 2021) — cited via the above
