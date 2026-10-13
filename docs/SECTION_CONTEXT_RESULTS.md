# Verified section-context v1 development results

Review date: 2026-10-12 EDT. Source: the researcher's completed Windows run and
uploaded `section-context-results.zip`, checked against the previously supplied
native cache, task manifest, original runs and delivered section implementation.

**Section context changes rankings and improves full MRR, but provides no evidence
coverage gain at the measured cutoffs.** Recall@5 remains 40.97%, any-hit remains
12/24, and complete coverage remains 8/24. None of the five multi-page questions
becomes complete at k=5. Expansion v1 remains the frozen development control.

## Artifact and execution verification

Internal run ID: `20261013T010312Z-967cd9567b9c`. The output folder was
`section-context-20261013T010312Z-1a0d48a0`; the differing suffix is expected because
folder naming and internal run IDs use separate GUIDs. Execution was October 12
at 21:03 EDT / October 13 at 01:03 UTC. Status complete and all three reproduction
flags are true. The uploaded ZIP contains all 11 requested files and passes CRC checks.

All ten output artifact SHA-256 hashes and sizes match the manifest. All recorded
input identities match the earlier supplied files, including the frozen task hash,
native cache, original manifest and expansion reference. The policies are unchanged:

| Policy | SHA-256 |
|---|---|
| Expansion v1 | `80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3` |
| Section v1 | `159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e` |
| Native cache | `c6de36446465cc9bdc27dfbf1dde2bc24c5cdd7f6b52a57b0f03fd7358d03a52` |
| Frozen tasks | `1d1bfa444a3041b3e51be9535ff276fc89fa3d7985231a0bd7f4aa6746395356` |

Executed Python source SHA-256
`fbb6792c37b47904c0e9e7f2d6f54bd412c8b7972bbeb498476a3bdaa42f6f67`
matches the delivered implementation with Windows CRLF newlines. The manifest records
dae9897 with an applied, uncommitted patch (`git_dirty=true`), not an unknown new
pushed implementation commit. Original Windows/Python/pypdf versions match the
recorded environment. The Git diff fingerprint is retained as provenance, but the
Python source fingerprint is the direct byte check on executed package code.

Independent review checks establish:

- Complete 12-report / 2,620-page context coverage and 24 minimal question records.
- All original/expanded query records and financial-expansion audits reproduce;
  no answer/justification/evidence fields appear in retrieval query inputs.
- All 2,620 context records reproduce exactly from source-only construction.
  Heading spans point to exact raw Unicode substrings; scopes are in range,
  inheritance points only one physical page backward, and caps/resets/summary agree.
- All 96 full rankings reproduce: 20,956 page scores checked, maximum absolute
  discrepancy 7.105427357601002e-15. Every report page remains a candidate; IDs are
  zero-based, scores finite/nonnegative and ties deterministic.
- Earlier original/stopword/expansion rankings and metrics match their verified
  reference outputs. Every section body score equals its frozen expansion score;
  heading scores and the 0.25-weighted sum also reproduce from the heading field.
- All per-question and aggregate metrics, full MRR, five-question subgroup metrics
  and deltas match independent rank/set arithmetic without using the project evaluator.

The original PDFs are not present here. PDF hashes are cross-checked against cache
and run provenance; the source PDFs are not rehashed or visually inspected during
this review. Exact context reproduction validates execution, not semantic heading
precision or PDF transcription quality. Source-only API separation, query allowlists
and the matching executed code support label exclusion; observing output alone
cannot prove arbitrary external process behavior. The implementation saves rankings
and context before parsing annotations for offline scoring.

## Paired results against frozen expansion v1

| Metric | Expansion v1 | Section v1 | Change |
|---|---:|---:|---:|
| Macro Recall@1 | 10.42% | 10.42% | 0 pp |
| Macro Recall@3 | 32.64% | 32.64% | 0 pp |
| Macro Recall@5 | 40.97% | 40.97% | 0 pp |
| Any-evidence hit@1 | 4/24 | 4/24 | 0 |
| Any-evidence hit@3 | 10/24 | 10/24 | 0 |
| Any-evidence hit@5 | 12/24 | 12/24 | 0 |
| Complete coverage@1 | 1/24 | 1/24 | 0 |
| Complete coverage@3 | 6/24 | 6/24 | 0 |
| Complete coverage@5 | 8/24 | 8/24 | 0 |
| Full-ranking MRR | 0.3024075204503773 | 0.31477955742883584 | +0.012372036978458567 |

At k=5, **all 24 question recalls and retrieved annotated-page sets are unchanged**.
There are no gains or regressions at that cutoff. Seventeen top-five ordered lists
change, including fourteen top-five candidate sets, but those substitutions do not
add annotated evidence. Non-gold pages are not automatically irrelevant because
the annotations are not an exhaustive relevance judgment.

At k=3, one gain and one regression cancel exactly. AMD quick-ratio question 00222
moves its gold balance-sheet page 55 from rank 5 to 3, changing Recall@3 from 0 to 1.
Best Buy acquisitions question 01077 moves gold page 50 from rank 3 to 4, changing
Recall@3 from 1 to 0. At k=1 all 24 recalls remain unchanged.

The MRR gain reflects nine improved first-evidence ranks, three regressions and
twelve unchanged. PepsiCo restructuring (01328, rank 3→2) and AMD quick ratio
(00222, 5→3) contribute most of the positive shift. Neither the new MRR nor the
unchanged page metrics establishes answer correctness.

| Task suffix | Topic | First evidence rank, expansion → section |
|---|---|---|
| 00222 | AMD quick ratio | 5 → 3 |
| 04417 | Best Buy inventory | 13 → 8 |
| 00517 | Boeing revenue categories | 97 → 86 |
| 00678 | Boeing gross margin | 17 → 14 |
| 00464 | Boeing cyclicality | 31 → 29 |
| 00585 | Boeing effective tax rate | 30 → 25 |
| 01009 | PepsiCo geographies | 20 → 13 |
| 00735 | PepsiCo legal battles | 133 → 98 |
| 01328 | PepsiCo restructuring | 3 → 2 |
| 01198 | AMD revenue change | 7 → 8 |
| 01077 | Best Buy acquisitions | 3 → 4 |
| 01091 | Boeing legal battles | 20 → 21 |

Across all 30 task/evidence-page references, 12 gold-page ranks improve, five regress,
and 13 stay fixed. This differs from the first-hit count because multiple evidence
pages contribute to some questions. The two PepsiCo calculation questions share
the same source pages and are not independent document examples.

## Five multi-page questions

Page IDs below are **zero-based physical PDF indices**; ranks are one-based.

| Task | Gold page ranks: expansion → section | Recall@5 in both | Complete@5 in both |
|---|---|---:|---:|
| 03069 AMD D&A margin | p55: 25→23; p59: 1→1 | 1/2 | No |
| 01290 Boeing customers | p7: 39→46; p9: 3→3; p13: 161→162 | 1/3 | No |
| 01009 PepsiCo geographies | p3: 228→228; p4: 20→13 | 0/2 | No |
| 03620 PepsiCo EBITDA less capex | p61: 23→19; p63: 1→1 | 1/2 | No |
| 04481 PepsiCo EBITDA margin | p61: 24→20; p63: 1→1 | 1/2 | No |

Multi-page macro Recall@5 remains 36.67%, any-hit remains 4/5 and complete coverage
remains 0/5. Subgroup full MRR rises 0.676667→0.682051 solely because PepsiCo
geography's first hit moves 20→13. This is deeper than the measured page cutoff.
The other four cases' first-hit ranks remain fixed despite missing-page rank changes.

### AMD: the separate revenue statement remains missing

Page 55 gains 0.484957 heading score after weighting, but remains rank 23. Page 59
gets 2.044810 and stays first. For this question, the operations-page heading field
matches only financial. The cash-flow field matches cash/flows and also equity from
an inherited stockholders' equity title covering the company-name opening before
the new cash-flow title. The query includes equity in its analyst-role wording.
That extra lexical match illustrates why source-provenance correctness does not
guarantee that every carried heading is semantically helpful. No D&A/revenue operand
combination or answer computation is performed.

### Boeing: detected headings do not match the customer wording

The three gold pages have **zero heading score** for this question. Their detected
headings mention airlines, government contracts, defense spending or risk factors;
the query asks primary customers of Boeing/FY2022. Literal token overlap is absent.
The body scores therefore stay fixed; other pages gain heading score and push
pages 7/13 farther down. Broader risk structure alone does not create a lexical
customer-category link. The three-page annotation requirement is preserved; no
alternative relevance labels or answer-specific hints are inserted into retrieval.

### PepsiCo geographies: continuation is correct, matching remains narrow

Page 4 inherits Our Operations over raw offsets [18,374), then changes to local
division headings, exactly as the prior review requested. The inherited title adds
no query match: operations differs from operates under the frozen unstemmed tokenizer.
Its weighted heading gain 0.473297 comes from the company term pepsico in the local
PepsiCo Beverages North America title. Page 3 has no matching heading token and
gets zero boost. Page 4 improves to 13 but neither page enters the top five.

### PepsiCo calculations: the missing dependency moves closer, but stays outside

For both numerical questions, page 61's heading matches income/statement and adds
2.345978 to its unchanged body score. Page 63 matches cash/flows/operating/statement
and adds 3.477775. The income statement improves by four positions in each question;
it still does not supply its Operating Profit/revenue rows within the top-five
annotated evidence set. Full first-hit MRR remains 1 because cash-flow page 63 is
first in both conditions. That metric cannot expose the missing second dependency.

For the traced EBITDA-less-capex question, the top five remain [63,46,53,76,54].
Page 61 rises 23.447328→25.793306 while fifth-place page 54 stays 37.851027;
the score gap narrows 14.403699→12.057721 without crossing the cutoff. Under these
same query/index statistics, even a hypothetical page-61-only boost at weight 1
would not pass the current fifth score. This arithmetic is not a new weight experiment;
it does not evaluate changing the weight for every competing page.

## Regression and detector limitations

The largest MRR regression is Best Buy acquisitions. Gold page 50 has no heading
match and keeps body score 6.756721. Page 49 contains Best Buy Gift Cards and other
accounting-policy headings; matching the company words produces heading score
5.705859, weighted gain 1.426465. Its total rises 5.753809→7.180274, moving it ahead
of the gold page. The first hit moves 3→4, causing the k=3 loss noted above.

Native page 50 actually has `2.   Acquisitions` at raw offset 1837, followed by acquisition
prose. Section v1 requires the word Note for numeric note headings and its generic
title rule rejects numeric prefixes. It misses that heading and also `3. Restructuring`,
leaving the earlier Stock-Based Compensation heading's recorded scope too broad.
Similarly, Boeing page 112 has `Note 22 – Segment and Revenue Information` with an
en dash. V1's note punctuation grammar supports colon/period/em dash/hyphen, not
en dash, so that heading is missed. No code is modified during this result review.

Source inspection also finds accepted table-label examples: Year Ended is treated
as a local title and carried onto the next statement; PepsiCo page 77's
`FLNA QFNA PBNA LatAm Europe AMESA APAC Corporate` column header is classified as
a generic title. These observed examples motivate precision/format auditing, but
do not estimate corpus-wide heading precision/recall. No PDF font/geometry check
was available to distinguish bold headings from table column text.

## Recorded structure and costs

| Quantity | Verified value |
|---|---:|
| Pages with heading tokens | 1,662 / 2,620 |
| Total added lexical heading tokens | 14,633 |
| Maximum tokens on a page | 64 |
| Included observed / inherited entries | 3,383 / 860 |
| Duplicate / cap rejections | 217 / 73 |
| Context artifact bytes | 1,908,325 |
| Entire comparison wall time | 1.924067 s |
| All-report context construction | 0.701294 s |
| Heading-index construction | 0.007643 s |
| Expansion / section query totals (24 questions) | 0.016828 / 0.029820 s |

The structural reset counts and byte/token summary reproduce. Body candidates,
source cache, expansion terms and body scores remain unchanged. The query totals
include the documented body/heading ranking and fusion work; full wall time also
includes original/stopword/expansion reproduction, validation, evaluation and output.
These are single fixed-order measurements, not p50/p95 latency, repeated speed
comparisons, GPU consumption or energy evidence. Native extraction is prior shared
ingestion. The context artifact is an unbounded full-document field store; the
per-page token cap does not make it a bounded condition-C ledger.

## Decision and handoff

Retain expansion v1 as the development control and preserve section v1 as this
completed, versioned ablation. The result supports a modest secondary ranking
effect, **not an improvement in the primary coverage metric or multi-page completeness**.
Do not silently retune the section weight or change note formats in the completed run.

Before a separately versioned refinement or ledger experiment, audit heading
precision, missed note forms and table/section boundaries using source-only samples
including non-evidence pages. The multi-page failures also show that a lexical
heading field does not coordinate financial operands or necessarily connect customer/
geography wording to source titles. Any adjacency, heading-type diversification,
query normalization or operand cue must be a declared separate change under the
same candidate/evidence-budget contract. None is implemented or evaluated here.

This is a small, label-exposed development pilot across four companies, with 24
questions and only five multi-page questions. It establishes neither answer
correctness, OCR quality, memory benefit nor held-out generalization.
This report and verification JSON contain gold-derived diagnostics: exclude them
from retrieval inputs, model prompts and ledger/correction memory.

The documentation-only `section-context-results.patch` applies after the already
applied implementation patch at dae9897. It updates README/current state, marks the
run guide verified, and adds this report; code, controls and run outputs are unchanged.
No experiment rerun or new dependency is needed to save these verified findings.

```powershell
Set-Location "$env:USERPROFILE\Downloads\Research-Seminar-OCR-current"
$resultsPatch = "$env:USERPROFILE\Downloads\section-context-results.patch"
git apply --check $resultsPatch
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; preserve local edits." }
git apply $resultsPatch
if ($LASTEXITCODE -ne 0) { throw "Results patch application failed." }
git diff --stat
```
