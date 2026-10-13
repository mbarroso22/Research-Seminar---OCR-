# Verified final note-format ablation and retrieval freeze recommendation

Review date: 2026-10-12 EDT. Source: the researcher's completed Windows run and
uploaded `note-format-results.zip`, compared with the previously verified native,
expansion-v1 and section-v1 outputs. The local user suite passed all 123 tests.

**Recommend freezing expansion v1 for the next matched native/OCR retrieval
comparison at k=5.** Note-format coverage improves valid source heading detection,
Best Buy acquisitions at smaller cutoffs, and full-ranking MRR. It adds no
annotated evidence at k=5, and all five multi-page questions remain incomplete.
Keep the note-format condition as the completed structural comparator. This
closes the planned heading-format ablations; proceed to rendering/OCR evaluation.

## Verification and scope

Internal run ID: `20261013T030434Z-320eab2ccfc7`. Output folder:
`note-formats-20261013T030434Z-7541d0a1`. Execution was October 12 at 23:04 EDT /
October 13 at 03:04 UTC. Different folder/internal suffixes are expected.
Status is complete; original, stopword, expansion and S1 reproduction flags
are all true. The ZIP passes CRC checks and contains the requested 14 files.

All **13 output hashes/sizes** and **25 input identities** match the manifest
and supplied original files. The native cache, 24-question task manifest,
minimal original/expanded queries, expansion audit and reference run lineages
remain fixed. Both S1 context files are byte-identical to the prior S1 run.

| Item | SHA-256 |
|---|---|
| Uploaded ZIP | `646c1a6d70b70b8b1eac64a812a6d09ef22ed76adce410dc81c9dc491d7b35ab` |
| Expansion v1 policy | `80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3` |
| Section v1 policy | `159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e` |
| Note-format policy | `cbbc145937e12535a3db7243a28c9eebf0c5d20f14e42b85fe4e5bd4b9cebb2a` |
| Native cache | `c6de36446465cc9bdc27dfbf1dde2bc24c5cdd7f6b52a57b0f03fd7358d03a52` |
| Frozen tasks | `1d1bfa444a3041b3e51be9535ff276fc89fa3d7985231a0bd7f4aa6746395356` |

The executed package fingerprint
`20d2c2da500565d2fae40ff2a3a45d003eedd815c3fe74ed02633cd6628fe40e`
matches the delivered implementation with Windows CRLF newlines. The manifest
records base `7ebb8f5ba533a7cd2533ef78c0c6dfd731bb9a1f` plus the applied uncommitted
patch (`git_dirty=true`), not a new pushed implementation commit. Runtime:
Windows 11, Python 3.13.7, pypdf 6.19.0. Git diff fingerprint is retained as
provenance; the source fingerprint verifies the executed Python package bytes.

Independent review reproduced all 2,620 S1 and 2,620 S2 context records, including
raw Unicode spans, detection audits, state transitions, scope bounds, caps and
one-page inheritance. It reproduced **120 full rankings / 26,195 page scores**
using a separate Counter/BM25 calculation, including both heading fields and
score components. Maximum absolute total-score difference was
`7.105427357601002e-15`. Every S1/S2 body score equals its expansion score exactly;
all report pages, blanks and attachments remain candidates with zero-based IDs.

Every per-question/aggregate metric, subgroup result, paired delta/count and
gold-page rank agrees with independent set/rank arithmetic without the project's
evaluator or paired-comparison helper. Original/stopword/E/S1 historical rankings
and metrics reproduce. Full non-gold page relevance is not asserted by this review.

Original PDFs are unavailable here: cache PDF provenance is cross-checked, but
PDFs are not rehashed or visually inspected. Source-context reproduction is not
measured semantic heading precision/recall. Matching executed code, minimal
source/query APIs and written-artifact ordering support label exclusion; output
inspection alone cannot prove arbitrary external process behavior. Answers,
justifications and evidence text never enter the retrieval projections; gold
pages are parsed for offline evaluation after retrieval artifacts are saved.
This report/recommendation is label-exposed development material and must remain
outside retrieval, OCR inputs, prompts, ledger and correction-memory inputs.

## Results against both frozen controls

E = expansion v1; S1 = original section v1; S2 = note-format coverage.
Macro Recall is averaged by question. Complete coverage requires every annotated
page, whereas Hit requires at least one. Cutoffs are fixed at 1/3/5.

| Metric | E | S1 | S2 |
|---|---:|---:|---:|
| Recall@1 | 10.42% | 10.42% | **14.58%** |
| Recall@3 | 32.64% | 32.64% | **36.81%** |
| Recall@5 (primary) | **40.97%** | **40.97%** | **40.97%** |
| Hit@1 | 4/24 | 4/24 | **5/24** |
| Hit@3 | 10/24 | 10/24 | **11/24** |
| Hit@5 | 12/24 | 12/24 | 12/24 |
| Complete@1 | 1/24 | 1/24 | **2/24** |
| Complete@3 | 6/24 | 6/24 | **7/24** |
| Complete@5 | 8/24 | 8/24 | 8/24 |
| Full MRR | 0.3024075204503773 | 0.31477955742883584 | **0.3470729345497992** |

S2 gains 4.1667 percentage points in macro Recall@1 and Recall@3 against each
control, with zero change in Recall/Hit/complete coverage at k=5. S2 minus S1
MRR is +0.03229337712096336; S2 minus E is +0.04466541409942193.
At k=5, all 24 per-question recalls **and annotated-page sets** stay unchanged.

### S2 minus S1: detector-format effect

One question gains at k=1 and k=3: Best Buy acquisitions 01077, gold p50,
rank **4→1**. No question loses Recall/Hit/complete coverage at any measured
cutoff. First-gold ranks improve for 3 questions, regress for 0 and stay fixed
for 21. Across 30 task/gold-page references, 3 improve and 27 stay fixed.
The acquisitions question supplies approximately 96.8% of the S2-minus-S1 MRR
increase, so the secondary gain is strongly concentrated in that one development case.

| Task | Topic | Gold rank S1 → S2 | Coverage consequence |
|---|---|---:|---|
| 01077 | Best Buy acquisitions | p50: 4 → 1 | Complete at k=1/3; already complete at k=5 |
| 01091 | Boeing legal battles | p112: 21 → 14 | Still outside k=5 |
| 00464 | Boeing cyclicality | p7: 29 → 28 | Still outside k=5; no new local p7 heading |

Only two top-five ordered page lists change: acquisitions reorders an existing
set, and AMD question 00917 replaces p64 with p59 at the fifth position. Its
gold p52 remains outside five, so that candidate substitution is not a measured
coverage gain. A page can change its score/rank because the report-wide heading
DF/average length changes even when its own local heading field is unchanged;
the cyclicality movement should not be attributed to detecting a new p7 title.

### S2 minus E: combined structural effect

At k=1 the gain is acquisitions, rank **3→1**. At k=3 the gain is AMD quick ratio
00222, p55 **5→3**, inherited from S1; acquisitions was already complete in E's
top three. Each cutoff has one gain, zero losses and 23 unchanged questions.
The same aggregate improvements against E and S1 therefore arise from different
paired changes at k=3. Do not attribute the AMD quick-ratio gain to note syntax.

First-gold ranks improve for 11 questions, regress for 1 and stay fixed for 12.
Across all 30 task/gold-page references, 14 improve, 3 regress and 13 stay fixed.
Seventeen top-five ordered lists and fourteen candidate sets change, without
adding or losing annotated evidence at k=5.

All first-evidence improvements versus E are listed below. Rows whose S1 and S2
ranks match are retained section effects, not gains caused by new note formats.

| Task | Topic | E → S1 → S2 first-evidence rank |
|---|---|---|
| 00222 | AMD quick ratio | 5 → 3 → 3 |
| 04417 | Best Buy inventory | 13 → 8 → 8 |
| 01077 | Best Buy acquisitions | 3 → 4 → 1 |
| 00517 | Boeing revenue categories | 97 → 86 → 86 |
| 01091 | Boeing legal battles | 20 → 21 → 14 |
| 00678 | Boeing gross margin | 17 → 14 → 14 |
| 00464 | Boeing cyclicality | 31 → 29 → 28 |
| 00585 | Boeing effective tax rate | 30 → 25 → 25 |
| 01009 | PepsiCo geographies | 20 → 13 → 13 |
| 00735 | PepsiCo legal battles | 133 → 98 → 98 |
| 01328 | PepsiCo restructuring | 3 → 2 → 2 |

| Regression relative to E | Gold rank E → S2 | Interpretation |
|---|---:|---|
| 01198 AMD revenue change | p42: 7 → 8 | Same regression as S1; p42 body/total score stays 4.056158 and heading score is zero; competitors receive context bonuses |
| 01290 Boeing customers | p7: 39 → 46; p13: 161 → 162 | Same regressions as S1; both gold heading fields have zero query overlap |

S2's note-format intervention introduces no additional gold-rank regression
relative to S1, but does not remove these combined structural regressions versus
E. All three affected pages remain outside five under every condition.

## Detection repairs and useful-query limits

Best Buy 2023 p50 now detects `2. Acquisitions` [1837,1854) and `3. Restructuring`
[3369,3387). The prior Stock-Based Compensation scope ends at 1837 rather than
4685; Acquisitions ends at 3369. Both notes enter the heading field. For 01077,
acquisitions is the useful literal match; restructuring is a boundary repair
without direct overlap. Body score stays 6.756720593087397. Heading score
4.037241018516054 adds **1.0093102546290136**, yielding 7.76603084771641 and rank 1.
The exact p43 notes parent enables the sequential chain; the p27 prose mention
does not. This repairs the previously identified smaller-cutoff S1 regression.

Boeing p111 now detects `Note 21 – Legal Proceedings` [2122,2149). The inherited
legal heading on p112 occupies [18,2429), ending at the newly detected Note 22
[2429,2470), rather than inheriting Fair Value Disclosures through [18,4088).
For 01091, p112's body score stays 4.912922568640251. Heading score
3.150166563905658 adds **0.7875416409764145**, giving 5.700464209616666 and rank 14
(E 20; S1 21). The fifth candidate scores 7.367275; the gap is approximately
1.666811. Correct legal-heading coverage supplies a real query bonus but does
not recover the annotated page within budget. Note 22 closes the legal scope;
its title has no legal-query overlap. P111 itself improves 37→26 relative to S1,
but is not the annotated evidence page for that task.

The frozen field is page-wide. A bounded span controls provenance/continuation;
it does not restrict a heading bonus to an extracted text chunk within that span.
Generic table-label and statement-prose false positives were intentionally left
unchanged. Exact recognition/scope improvement and top-five retrieval recovery
remain distinct findings.

## Five multi-page questions

Physical PDF page IDs are zero-based; ranks are one-based. Every S2 gold-page
rank and annotated top-five set for these questions is unchanged from S1.

| Task | E gold-page ranks | S1 = S2 gold-page ranks | Recall@5, all conditions |
|---|---|---|---:|
| 03069 AMD D&A margin | p55: 25; p59: 1 | p55: 23; p59: 1 | 1/2 |
| 01290 Boeing customers | p7: 39; p9: 3; p13: 161 | p7: 46; p9: 3; p13: 162 | 1/3 |
| 01009 PepsiCo geographies | p3: 228; p4: 20 | p3: 228; p4: 13 | 0/2 |
| 03620 PepsiCo EBITDA less capex | p61: 23; p63: 1 | p61: 19; p63: 1 | 1/2 |
| 04481 PepsiCo EBITDA margin | p61: 24; p63: 1 | p61: 20; p63: 1 | 1/2 |

Subgroup macro Recall@5 stays **36.67%**, Hit@5 stays **4/5**, and Complete@5
stays **0/5**. MRR is E 0.6766666666666666 and S1/S2 0.6820512820512821.
That first-hit metric obscures the missing second financial dependency.

The earlier bottleneck separation still applies: AMD's correct operations
statement wording has weak literal query matching; Boeing customer headings
have zero overlap; PepsiCo Operations/operates do not match literally; the
PepsiCo income statement receives useful signal but remains outside five.
These cases were not missing en-dash/bare-note detections. Better note syntax
does not establish a remedy for vocabulary or multi-statement selection.

## Context changes and measured cost

S2 observes 39 new en-dash headings and accepts 17 bare numbered notes. Of 271
bare-pattern candidates, 248 are outside an eligible region, 4 are on contents
pages and 2 fail sequential numbering. These source diagnostics cover the
development cache and are not manually annotated precision/recall estimates.

Actual context differs on 57 pages: Boeing 2022 26, AMD 2022 15, Best Buy 2023
12, Best Buy 2015 2 and Best Buy 2019 2. All 2,620 pages are still emitted.
The existing false contents reset at Best Buy 2015 p74 and split-note formats
in Best Buy 2019 remain conservative coverage limits, as specified pre-run.

| Context measure | S1 | S2 |
|---|---:|---:|
| Pages with heading tokens | 1,662 | 1,667 |
| Total heading tokens | 14,633 | 14,887 |
| Maximum tokens/page | 64 | 64 |
| Included observed headings | 3,383 | 3,440 |
| Included inherited headings | 860 | 861 |
| Duplicate rejections | 217 | 216 |
| Cap rejections | 73 | 73 |
| Serialized context bytes | 1,908,325 | 2,534,625 |

Serialized S2 context is +626,300 bytes (+32.82%), including recognition audit
metadata; this is not solely index size or model context size. Detection counts
and admitted heading counts differ because inheritance, duplicates and cap
competition can change. Added note number/Note tokens follow the unchanged
tokenizer; they were not stripped after inspecting results.

The same Windows run records 3.067642 seconds total wall time including all
control reproduction, validation, serialization and offline scoring. S1 context
construction is 0.698179 s; S2 is 0.999540 s. S1/S2 heading-index times on queried
reports are 0.008349/0.006128 s. Total query times for 24 questions:
E 0.016589 s, S1 0.031507 s and S2 0.029583 s.

These single fixed-order measurements are descriptive stage logs, not repeated
latency, throughput or energy benchmarks. They cannot establish that S2 is faster
than S1, nor that 3.067642 s is a standalone S2 pipeline cost. E avoids the extra
heading construction/indexing; the freeze decision also considers its simpler
representation comparison. No cost per correct answer can be computed without
answer extraction/correctness evaluation.

## Recommendation and OCR transition

Carry forward **expansion v1** as the frozen retrieval baseline at the predeclared
five-page budget. Preserve its existing policy snapshot and all historical
controls. It reaches the same primary Recall@5, Hit@5 and complete coverage as
S2 with no heading dependency. This is a protocol-specific recommendation:
S2's top-one/top-three and MRR improvements are real and must be retained in the
findings. They do not supply extra annotated evidence to the current top-five
answer input or resolve multi-page coverage. The 24-question development set
cannot establish held-out superiority of either method.

Keep S2, which improves S1 without a gold-rank regression, as the saved structural
comparator for later matched context work. Do not silently substitute it into
condition A or begin another heading-format tuning round. The recommendation
record is `docs/RETRIEVAL_BASELINE_RECOMMENDATION.json`; it references the unchanged
`docs/EXPANSION_V1_CONTROL.json`. Results/review records are documentation, not
runtime retrieval inputs. No executable policy changes accompany this results update.

The next implementation milestone is **full-report rendering and an OCR adapter
smoke test**, rather than another native heading experiment:

1. Preserve the 12 reports/2,620 pages/24 tasks and source PDF hashes. Freeze E's
   query expansion/stopwords/BM25/ties/full-report candidates/k=1/3/5 for matched
   representation evaluation. No new query terms, labels or corrections enter
   OCR or retrieval. Final evidence is at most five pages under the protocol;
   answer token/image budgets remain separate and unimplemented.
2. Implement/validate full-report resumable rendering. Existing `render-pages`
   is evidence-only. Follow the roadmap's 200-DPI RGB proposal, inspect small
   numbers/footnotes and a small 300-DPI comparison before fixing resolution.
   Log renderer/version, PDF/page ID, dimensions, DPI, rotation, image hash,
   disk cost and failures. Keep printed labels separate from physical indices.
3. Verify hardware/runtime compatibility, pin one standard OCR engine/adapter
   and smoke-test representative pages, then the 25 distinct gold evidence
   pages as an explicit **oracle evidence diagnostic**. Preserve raw OCR,
   boxes/confidence where available, checkpoint/runtime/device and initialization/
   page timings. Review numerical signs, units, years and table reading order.
   Native/evidence text is not perfect full-page transcription; manually verify
   a subset before claiming CER/WER. Engine/version selection is pending, not
   established by this run.
4. OCR complete reports with resumable failures/blank accounting and run frozen
   E on native versus OCR page text. Match PDFs, questions, page candidates,
   evaluation labels and cutoffs; never evaluate full-report recall on only
   known evidence pages. If resources limit scale, use one complete short
   annotated report as a declared smoke milestone without changing the pilot
   or making full-pilot claims.
5. Review representation-driven retrieval/numeric errors and shared ingestion
   costs before fixed answer extraction/citation scoring. Section/ledger and
   held-out studies remain separate later comparisons. This native result is
   neither OCR quality, answer accuracy, learned memory nor energy evidence.
