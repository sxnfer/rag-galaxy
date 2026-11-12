# Results

Real numbers only, copied from command output. Failures are recorded too.
Each entry: date, what ran, on which data, the exact numbers.

## Skeleton check (2026-11-06)

Run on 2 synthetic test PDFs (backend/tests/fixtures), with the word-counting
stand-in embedder, in Claude's sandbox. Proves the plumbing only; not results.

- `register` twice: 2 new, then 0 new and 2 already registered (idempotent).
- `parse`: synthetic PDD 4 pages, 7 headings, 1 table; the image-only page was flagged as scanned.
- `chunk --chunker fixed --size 100`: 8 chunks.
- `hnsw`: recall@5 vs exact 1.000 at ef_search 10/40/100 (8 chunks, so trivially exact).
- `eval` and `ask`: ran end to end; generation skipped (no API key in the sandbox).

## M1 Collect

### 2026-11-08: first real PDFs

Data: 12 real PDFs from public copies outside the CDM site (URLs in `data/raw/SOURCES.csv`).
These are not the 3 seed projects: their PDFs are on cdm.unfccc.int, which needs hand downloads.

- `register`: 12 new, 0 already registered. Second run: 0 new, 12 already registered.
- Mix: 5 PDDs, 6 validation reports (3 are versions of one Paraíso report), 1 registration form.
- NOT tested on real data: `parse_project_page` and `collect --offline`, because no project page has been saved yet.

## M2 Parse

### 2026-11-08: 12 real PDFs

- `parse`: 12 of 12 documents, 719 pages, 789 tables, 168.77 s. No crashes.
- Flags: 0 scanned, 0 garbled, 1 empty, 11 short.
- MuPDF printed "format error: No default Layer config" on 2 Paraíso PDFs; both still parsed.
- Failure: headings are over-detected, about 8 per page (5,841 in total). Most common: "CDM – Executive Board" 253, "Concl" 220, "PROJECT DESIGN DOCUMENT FORM (CDM PDD) - Version 03" 166, "Final" 117, "Draft" 117. These are page headers and table labels, not sections.

## M3 Chunk + search

### 2026-11-08: fixed vs structure, size 300, BAAI/bge-small-en-v1.5

| Run | Chunks | Median words | Under 20 words | 5 words or fewer | Max words | Time |
|---|---:|---:|---:|---:|---:|---:|
| fixed/300 | 861 | 300 | 0 | 0 | 300 | 60.67 s |
| structure/300 | 4,937 | 25 | 2,172 | 962 | 748 | 408.84 s |

- Failure: the structure run fragments badly because of the heading over-detection in M2.
- HNSW recall@5 vs exact: 1.000 at ef_search 10, 40 and 100 for both runs. Index built in 0.13 s (fixed) and 0.40 s (structure).
- Caution: that recall is weak evidence. It used 50 random chunks as queries on a small dataset, because the golden set is empty.

## M4 Retrieval quality + answers

### 2026-11-08: 6 hand-picked questions, retrieval only

Top 5 hits for each question, read by hand. Not a formal score. Generation was skipped: `ANTHROPIC_API_KEY is not set`.
`eval` did not run: "The golden set is empty".

| Question | Fixed | Structure |
|---|---|---|
| Methodology of Pedra do Reino III | Found: ACM0002 at ranks 2 and 5, but 3 of 5 hits are from sister project Pedra do Reino | Found: ACM0002 at rank 1, but 3 of 5 hits are from the sister project |
| Installed capacity of Cabeço Preto IV | Found: 19.8 MW at ranks 3 and 4; the rank 1 chunk doesn't contain it | Found: 19.8 MW at rank 1 |
| Annual emission reductions of Song Bung 6 | Failed: only 2 of 5 hits from Song Bung, neither with the figure; the report has 478,975 tCO2e over 7 years on p. 34 | Failed: 0 of 5 from Song Bung; all 5 are the same 3-word heading "B.6. Emission reductions:", and 4 were dropped as duplicates |
| Who validated Baguari | Found: SGS, top hits all from Baguari | Found: SGS, top hits all from Baguari |
| Methodology of Putian Houhai (not in the data) | Failed to refuse: 5 unrelated hits, scores 0.624 to 0.631 | Failed to refuse: 5 unrelated hits, scores 0.652 to 0.689 |
| Carbon price paid in 2023 (not in the documents) | Failed to refuse: 5 unrelated hits, scores 0.641 to 0.670 | Failed to refuse: 5 unrelated hits, scores 0.699 to 0.705 |

## Arsenal: cards only vs cards + rank (plan v2, 1d)

### 2026-11-11: built, not yet measured

No numbers yet. The code was written on a machine with no Docker or Postgres, so `chunk`, `eval` and `bake`
have not run for the Arsenal. What is known so far comes from unit tests only (`backend/tests/test_arsenal.py`):

- `weapons.csv`: 48 weapons, 7 classes, passes every check in `collect/table.py`; 286 cards.
- With every card as a candidate (perfect retrieval), the rank stage returns exactly the expected weapons
  for all 17 stat questions in the golden set. That proves the rules and the table agree. It says nothing
  about what search really retrieves.

To fill this in: `python -m pipeline register --library arsenal`, `chunk --library arsenal`, `eval`.
`eval` prints two Arsenal rows from the same 20 candidates per question: "cards" (similarity order) and
"cards + rank". Copy both here with recall@5 and MRR over the 18 answerable questions, and note which
questions the rank stage could not fix because search never returned the right weapon.

### 2026-11-12: measured, then retired

Run on the Mac (Docker + Postgres), BAAI/bge-small-en-v1.5, 286 cards, 20 candidates, exact search,
18 answerable questions:

| run | recall@5 | MRR |
|---|---|---|
| cards (search alone) | 0.463 | 0.574 |
| cards + rank | 0.852 | 0.951 |

HNSW recall@5 vs exact: 1.000 at ef_search 10, 40 and 100. The four examples were baked (each answer
passed the citation check). One answer to note: "close range weapon highest damage" came back with a single
sniper rifle, because the rank stage sorted by damage alone, and sniper rifles hit hardest at every range.

The same day the Arsenal and the carbon documents were retired in favour of the electric car library.

## Electric cars: cards only vs cards + rank

### 2026-11-12: first run

Data: `data/seeds/ev/vehicles.csv`, 231 battery-electric cars of the 2026 model year from the EPA
(`data/seeds/ev/SOURCE.md`). 1,155 cards (5 per car: overview, range, efficiency, running cost, charging).
BAAI/bge-small-en-v1.5, exact search, 20 answerable golden questions (plus 2 the table can't answer).

- `register`: 231 rows, every check in `collect/table.py` passed (including MPGe agreeing with kWh per 100 miles).
- `hnsw`: recall@5 vs exact 1.000 at ef_search 10, 40 and 100 (22 golden questions).

How many candidates search hands to the rank stage (cards + rank, same 20 questions):

| candidates | recall@5 | MRR |
|---|---|---|
| 20 | 0.450 | 0.600 |
| 50 | 0.708 | 0.800 |
| 100 | 0.892 | 1.000 |
| 200 | 1.000 | 1.000 |
| 400 | 1.000 | 1.000 |

Every miss at 50 was a question about the best of the whole table ("which electric car has the longest
range?", "most efficient sedan"): the winner's card was not among the 50 that sounded most like the
question, and rank can only sort what it is given. 200 was chosen (about a sixth of the 1,155 cards).

With 200 candidates:

| run | recall@5 | MRR |
|---|---|---|
| cards (search alone) | 0.308 | 0.326 |
| cards + rank | 1.000 | 1.000 |

Read this with care: the golden answers were written from the table with the same intent rules the rank
stage uses (a unit test checks they agree). So 1.000 says search's 200 candidates always contained the
winners, and that the rules read these 20 questions as intended. It does not say the rules understand
questions phrased in ways nobody wrote down. The next golden questions should come from real visitors.

Baked examples (Claude Haiku 5.5, every answer passed the citation check): "longest range electric SUV",
"most efficient small car", "cheapest electric pickup to run", "a small electric car for city driving".
A first try at a no-stat example, "a roomy electric car for a big family", answered NOT_FOUND: correct,
since the EPA data has no seats or boot space, but a poor example, so it was replaced.

## M5 Deploy
