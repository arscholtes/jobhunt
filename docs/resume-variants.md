# Resume variants and the gate

## Shape of the thing

```
resume.toml            one copy of every fact, tagged by where it applies
   │
   ├── jobhunt/gate.py     posting -> (role shape, domain) + eligibility flags
   └── jobhunt/resume.py   (shape, domain) -> a selection and ordering of the facts
```

`jobhunt resume <job-id>` runs both: gate the posting, render the cell.
`jobhunt gate <job-id>` shows the decision and its reasoning without rendering.

## Why a matrix, and why it is generated

Two axes, because neither determines the other. Measured on the live corpus
(1,839 postings, 206 scoring ≥ 45):

| role shape | share | | domain | share |
|---|---|---|---|---|
| generic | 31.1% | | ai / llm | 41.3% |
| backend | 28.6% | | ruby / rails | 36.4% |
| platform | 15.0% | | developer tools | 28.6% |
| fde | 13.1% | | multi-tenant saas | 4.9% |
| fullstack | 12.1% | | | |

5 shapes × 4 domains = 20 cells, and all 20 occur in the shortlist. A Senior
Software Engineer at an LLM-infrastructure company and one at a logistics SaaS
share a title and want different evidence first; title alone cannot separate them.

The cells are **generated from `resume.toml`, never hand-maintained**. Eight
hand-written documents would cover 58% of the shortlist and require every
correction to be applied eight times. Generated, twenty cells cover 100% and a
correction is applied once. This is the whole reason the fact base exists.

## What varies, and what never does

**Varies per cell:** the summary line, the order of skill groups and the terms
inside them, which bullets appear and in what order, which projects appear.

**Never varies:** construction. Single column, no tables, no sidebars, contact
details in the body, standard section headings, real selectable text. This is
fixed because it is the only resume failure mode that has actually been measured
— two-column layouts scrambled in 7 of 8 ATS parsers, table content dropped in 5
of 8, header/footer text ignored, image-based text losing name and contact
details every time. See `resume-research.md`.

Nothing is ever invented or hidden per cell. A variant reorders evidence; it does
not make claims the fact base does not contain.

## Selection rules

- **Eligibility** — a bullet with no `shapes` is eligible for every shape; one
  with no `domains` is eligible for every domain. Tag only to *restrict*.
- **Order** — `weight` first, shape match and domain match as tiebreakers. Weight
  is your judgment of how good the material is and outranks relevance: an
  untagged weight-10 bullet beats a shape-tagged weight-8 one. An earlier
  additive-bonus version got this backwards and pushed the strongest bullet off
  the page.
- **Summary** — most specific wins: `shape.domain`, then `shape`, then `default`.
- `BULLETS_PER_ROLE` in `resume.py` caps bullets per role.

## Flags

Eligibility is **displayed, never applied**. The gate does not hide a posting; it
tells you what you are walking into, quoting the text that triggered it so a false
positive is visible as one.

| flag | shortlist rate | meaning |
|---|---|---|
| `equivalency_ok` | 6.8% | degree language explicitly satisfied by experience |
| `degree_hard` | 2.9% | degree required with no equivalency clause |
| `degree_soft` | 0.5% | degree named only to be waived — not a gate |
| `level_above` | 2.4% | staff/principal role behind a non-staff title |
| `region_locked` | 2.4% | region restriction the location field does not state |
| `level_below` | 1.5% | new-grad / early-career role |

15.0% of the shortlist raises at least one.

### These patterns were wrong until they were measured

Every flag pattern here started out matching ordinary English and had to be
tightened against the corpus:

- `level_above` matched 34 postings, of which **19 were the plain English words**
  — "engineering at Privy is *distinguished by*", "manage and *architect*
  multi-tenant infrastructure". 56% false positive. Now the term must sit beside
  a role noun or an explicit level phrase. 34 → 5, all genuine.
- `degree_hard` fired on "MS is helpful but **not required**" — a degree named to
  be waived, matched as a hard gate. `degree_soft` now claims those first.
- Postings arrive as HTML and the entity debris matched: an unstripped `&nbsp;`
  leaves the literal `bsp`, whose `bs` hit the degree pattern. `_hay` strips tags
  and entities.
- `level_below` was then tightened too far and missed a New Grad posting scoring
  92. Level terms are unambiguous in a *title* and ambiguous in a *body* ("unlike
  a new grad, you will…", "mentor junior engineers"), so the title is matched
  loosely and the body only on an explicit statement about the role.

The general rule: a regex over human prose is a hypothesis until it is run
against the corpus and the matches are read.

## Known precedence choices

`SHAPES` and `DOMAINS` in `gate.py` are ordered tables, first match wins.
Reordering them is the intended way to tune, and two calls are worth knowing:

- `platform` is listed before `product`, so "Product Engineer, Product Platform"
  gates to `platform`. Both readings are defensible; swap the rows if the product
  reading should win.
- `ai` outranks `rails` — the stack shows up in the skills section either way, but
  the domain framing only gets said once, in the summary.

A title naming no engineering role at all (1.9% of the shortlist — "Security
Operations Lead", "Data Scientist, Product") does not get its body read for
shape, and gates to `generic`. Before that guard, "Operations Associate, New Grad"
classified as `platform` on the word "infrastructure" appearing in its body.

## Not done

- `resume.toml` is a **draft**. Title, dates and prior roles are `TODO`; the
  Liftify bullets were derived from work Alex is on record as having done and
  need verifying rather than trusting. No bullet carries a real number yet.
- The gate's shape classifier is the same one the scorer needs for its known
  role-shape blindness (security and frontend score well because the JS/React
  weights match, with nothing encoding "backend/platform, not frontend"). It is
  deliberately a standalone module so `score.py` can consume it. **Not wired in** —
  that is a scorer change, not a resume change.
