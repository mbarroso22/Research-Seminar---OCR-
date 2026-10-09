# Verified question-only financial-term expansion results

The fixed expansion policy increased macro evidence Recall@5 from **30.56% to 40.97%** against the stopword control on the same 24-question development pilot. Any-evidence Hit@5 rose from **9/24 to 12/24**, and complete coverage rose from **6/24 to 8/24**. Three questions gained top-five recall; none regressed at that cutoff. All five multi-page questions still lack complete top-five coverage.

## Run and verified scope

- New run: `20261009T020622Z-76a16239e13d`; 2026-10-08 22:06:22–22:06:23 America/New_York (2026-10-09 02:06 UTC).
- Original run: `20261008T051510Z-7b1970c7f4e8`; stopword reference: `20261009T012131Z-1e32aa99fc79`.
- Same fixed development pilot: 12 reports, 2,620 physical pages, 24 questions across six annotated reports. Six other reports support processing coverage, not QA scoring.
- Shared native representation: 2,613 nonempty pages, seven empty native-text pages, no failed pages.
- Complete within-report page candidates and zero-based PDF IDs are preserved in all three conditions.
- Fixed `financial-question-terms-v1` policy expanded six questions. All 18 untransformed questions have exactly the same full ranking and scores as the stopword condition.
- No failed, partial-extraction, or no-match questions in any condition.

## Aggregate metrics

Recall is macro evidence-page recall: the fraction of annotated pages retrieved per question, averaged over all 24 questions. Any hit needs at least one annotated page; complete coverage needs every annotated page. These score evidence retrieval, not answers.

| k | Metric | Original BM25 | Stopwords | Question expansion |
|---|---|---:|---:|---:|
| 1 | Macro evidence recall | 6.25% | 8.33% | 10.42% |
| 1 | Any-evidence hit | 8.33% | 12.50% | 16.67% |
| 1 | Complete evidence coverage | 4.17% | 4.17% | 4.17% |
| 3 | Macro evidence recall | 20.14% | 26.39% | 32.64% |
| 3 | Any-evidence hit | 25.00% | 33.33% | 41.67% |
| 3 | Complete evidence coverage | 16.67% | 20.83% | 25.00% |
| 5 | Macro evidence recall | 28.47% | 30.56% | 40.97% |
| 5 | Any-evidence hit | 33.33% | 37.50% | 50.00% |
| 5 | Complete evidence coverage | 25.00% | 25.00% | 33.33% |

| Metric | Original BM25 | Stopwords | Question expansion |
|---|---:|---:|---:|
| Full-ranking MRR | 0.208245 | 0.246135 | 0.302408 |

The primary comparison is expansion versus stopwords: **+10.42 percentage points Recall@5**, +12.50 points any-evidence hit, +8.33 points complete coverage, and +0.056273 full-ranking MRR. Against original BM25, Recall@5 improves by +12.50 points; that combined effect includes the earlier stopword change and cannot be attributed solely to expansion.

| Top-five outcome | Original BM25 | Stopwords | Question expansion |
|---|---:|---:|---:|
| No annotated evidence | 16 | 15 | 12 |
| Partial evidence | 2 | 3 | 4 |
| Complete evidence | 6 | 6 | 8 |

## Where the gain comes from

Ranks are one-based; page IDs are zero-based. All six transformed questions are listed.

| Question | Report / metric | Evidence page(s) | Stopword rank(s) | Expanded rank(s) | Top-five consequence |
|---|---|---|---|---|---|
| 00222 | AMD 2022 quick ratio | 55 | 113 | 5 | New complete annotated coverage |
| 00917 | AMD 2022 operating margin | 42 | 6 | 3 | New complete annotated coverage |
| 00685 | Best Buy 2023 gross margin | 39 | 59 | 29 | Still misses at k=5 |
| 00678 | Boeing 2022 gross margin | 54 | 82 | 17 | Still misses at k=5 |
| 03620 | PepsiCo 2022 EBITDA less capex | 61, 63 | 17, 1 | 23, 1 | Still partial; page 61 regresses |
| 04481 | PepsiCo 2022 EBITDA margin | 61, 63 | 33, 14 | 24, 1 | New partial coverage; page 61 still missing |

The two AMD questions each contribute 1/24 to the macro gain; the PepsiCo EBITDA-margin question contributes 0.5/24. Their sum is 2.5/24 = +10.42 percentage points. The quick-ratio evidence is exactly at rank 5, so it does not count as a top-three gain.

The same gross-margin vocabulary moves both inspected statement pages up the ranking without bringing either into the top five. This supports a limited statement-localization benefit, not a conclusion that metric retrieval is solved. The six transformations are heterogeneous: for PepsiCo EBITDA less capex, the missing operations page falls from rank 17 to 23. No top-five recall loss does not mean every evidence-page rank improved.

## Paired recall and multi-page coverage

| k | Improved vs stopwords | Regressed | Unchanged |
|---|---:|---:|---:|
| 1 | 1 | 0 | 23 |
| 3 | 2 | 0 | 22 |
| 5 | 3 | 0 | 21 |

All five multi-page questions remain incomplete at k=5. Complete coverage gains come from two single-page annotation sets. First-hit MRR cannot diagnose this completeness failure on its own. The 12 remaining top-five misses and four partial cases need separate analysis; some unannotated retrieved pages could still be relevant because FinanceBench annotations are not exhaustive relevance judgments.

## All questions: evidence ranks

Question IDs use their final numeric suffix. Entries are `zero-based page: one-based rank`.

| Question | Report | Stopword page:ranks | Expanded page:ranks | Recall@5 stopwords → expansion |
|---|---|---|---|---|
| 03069 | AMD_2015_10K | 55:25, 59:1 | 55:25, 59:1 | 0.500 → 0.500 |
| 00222 | AMD_2022_10K | 55:113 | 55:5 | 0.000 → 1.000 |
| 00995 | AMD_2022_10K | 3:8 | 3:8 | 0.000 → 0.000 |
| 01198 | AMD_2022_10K | 42:7 | 42:7 | 0.000 → 0.000 |
| 00917 | AMD_2022_10K | 42:6 | 42:3 | 0.000 → 1.000 |
| 01279 | AMD_2022_10K | 57:4 | 57:4 | 1.000 → 1.000 |
| 00563 | AMD_2022_10K | 47:1 | 47:1 | 1.000 → 1.000 |
| 00757 | AMD_2022_10K | 11:51 | 11:51 | 0.000 → 0.000 |
| 04417 | BESTBUY_2019_10K | 51:13 | 51:13 | 0.000 → 0.000 |
| 00685 | BESTBUY_2023_10K | 39:59 | 39:29 | 0.000 → 0.000 |
| 01077 | BESTBUY_2023_10K | 50:3 | 50:3 | 1.000 → 1.000 |
| 01275 | BESTBUY_2023_10K | 41:2 | 41:2 | 1.000 → 1.000 |
| 00517 | BOEING_2022_10K | 61:97 | 61:97 | 0.000 → 0.000 |
| 01091 | BOEING_2022_10K | 112:20 | 112:20 | 0.000 → 0.000 |
| 00678 | BOEING_2022_10K | 54:82 | 54:17 | 0.000 → 0.000 |
| 01290 | BOEING_2022_10K | 7:39, 9:3, 13:161 | 7:39, 9:3, 13:161 | 0.333 → 0.333 |
| 00464 | BOEING_2022_10K | 7:31 | 7:31 | 0.000 → 0.000 |
| 00494 | BOEING_2022_10K | 8:3 | 8:3 | 1.000 → 1.000 |
| 00585 | BOEING_2022_10K | 54:30 | 54:30 | 0.000 → 0.000 |
| 01009 | PEPSICO_2022_10K | 3:228, 4:20 | 3:228, 4:20 | 0.000 → 0.000 |
| 00735 | PEPSICO_2022_10K | 25:133 | 25:133 | 0.000 → 0.000 |
| 01328 | PEPSICO_2022_10K | 77:3 | 77:3 | 1.000 → 1.000 |
| 03620 | PEPSICO_2022_10K | 61:17, 63:1 | 61:23, 63:1 | 0.500 → 0.500 |
| 04481 | PEPSICO_2022_10K | 61:33, 63:14 | 61:24, 63:1 | 0.000 → 0.500 |

## Verification and provenance

All eight uploaded files were read directly from their supplied local copies. The seven output artifact byte sizes and SHA-256 values match the new manifest. Both earlier run identities, baseline manifest checksum, stopword reference manifest checksum/artifact hashes, original input hashes, and frozen annotation checksum match the prior verified files.

The original query projection contains exactly `task_id`, `doc_id`, and `question` and matches the frozen task questions. Each expanded query and each audit record was regenerated from that question projection using the delivered policy; every result matches. Both query files retain only the three permitted fields. Expansion adds no answers, justification, evidence labels, source values, or manually selected page cues. The full policy record matches the delivered code, including the rule list, cap, and algorithm description.

Policy SHA-256: `80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3`. The manifest records checkout `3550ba2f352a9be216455275559fbf0c9bbc3a1e` with local changes. Package source SHA-256 `bb3986de16e85d6b0e6f2d8030be0ef06e2dc797c2fb018c2f50820ea4300a38` matches the delivered implementation with Windows CRLF line endings; the revision alone would not identify the executed uncommitted code.

All three 24-question prediction sets have complete report-scoped page rankings, valid zero-based page IDs, finite nonnegative scores, and deterministic tie order. Both controls reproduce their earlier full rankings/scores within 1e-12 relative/absolute tolerance. All 18 untransformed queries preserve the stopword rankings/scores. Every per-question recall/hit/coverage value, aggregate, full-ranking MRR, and reported delta was recalculated independently from frozen evidence IDs without invoking the pipeline evaluator.

The full native-page cache and PDFs were not uploaded for this review. Their checksums and full-cohort validation are recorded by the completed runner; expanded BM25 scores were not independently recomputed from the entire cache locally. Supplied ranking metrics and query transformations were independently verified.

## Cost observations and limits

The recorded new-run wall time is 1.014 s and includes input validation, query expansion, both control reproductions, ranking, scoring, and output overhead. Initial validation: 0.0327 s; question transformation across all 24 queries: 0.0035 s.

Indexing: original 0.255 s; stopwords 0.261 s. Expanded retrieval shares the stopword index, so its incremental index-building time is zero by construction. Query totals: original 0.0323 s, stopwords 0.0154 s, expansion 0.0165 s. The prior PDF extraction cost remains shared ingestion cost.

These are a single fixed-order cached-text run, not repeated end-to-end latency or measured energy results. Runtime: Windows 11, Python 3.13.7, pypdf 6.19.0. The original 12-report ingestion is reused rather than eliminated.

The policy was designed after labeled development diagnostics. The gain is descriptive for this 24-question pilot; it establishes no statistical significance, held-out generalization, OCR accuracy, answer correctness, numerical operand/unit/year correctness, or bounded-memory contribution. Native text remains an unverified extraction reference.

## Next research decision

Freeze and retain all three conditions and the v1 expansion policy. The expansion result supports continuing with this control in development, while keeping the original and stopword baselines available. Further tweaks to this same labeled pilot remain development tuning.

The next proposed structural ablation is source-derived financial-statement/section context with explicit heading source pointers, added separately to a fixed retrieval control. Focus on whether it retrieves missing statement pages and complete multi-page evidence at the same five-page cutoff. Freeze heading detection, continuation limits, and ranking rules before running; audit weak headings and boundary mistakes. Do not add section cues, adjacency, and ledger memory together and attribute their combined gain to memory.

Before a held-out claim, define company/document evaluation groups and preserve their annotations from rule/prompt/context selection. Full-report OCR and the later A/B/C context/ledger comparison remain separate roadmap stages. No new structural experiment, OCR engine, or answer generator has executed in this review.
