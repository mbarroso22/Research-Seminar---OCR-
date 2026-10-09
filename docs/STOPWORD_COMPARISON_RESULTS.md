# Verified native BM25 stopword comparison

Stopword filtering produced a small evidence-retrieval gain on the 24-question development pilot. The original rankings reproduce, and every uploaded artifact hash and independently calculated metric matches. At k=5, the improvement comes entirely from retrieving one additional evidence page for one two-page AMD question; complete-evidence coverage did not improve.

## Run and scope

- Comparison: `20261009T012131Z-1e32aa99fc79`; baseline: `20261008T051510Z-7b1970c7f4e8`.
- Executed 2026-10-08 at 21:21:31–21:21:32 America/New_York (2026-10-09 01:21 UTC).
- Same 12-report / 2,620-page pilot; 24 questions across six annotated reports. Six other reports support processing coverage, not question scoring.
- Native text reused from the completed original run: 2,613 nonempty pages, seven empty native-text pages, no failed pages.
- Candidate pages remain all physical pages within the question’s specified report, with zero-based PDF IDs.
- Only change: the fixed `english-function-words-v1` list is filtered from page and question tokens. BM25 k1=1.2 and b=0.75; no stemming, query expansion, year change, or candidate restriction.
- No failed, partial-extraction, or no-match questions in either condition.

## Independently verified aggregate results

Recall is the mean fraction of annotated evidence pages retrieved per question. Any hit requires at least one annotated page; complete coverage requires every annotated page. All denominators contain all 24 questions. Deltas are percentage points.

| k | Metric | Original | Stopwords | Delta (pp) |
|---|---|---:|---:|---:|
| 1 | Macro evidence recall | 6.25% | 8.33% | +2.08 |
| 1 | Any-evidence hit | 8.33% | 12.50% | +4.17 |
| 1 | Complete evidence coverage | 4.17% | 4.17% | +0.00 |
| 3 | Macro evidence recall | 20.14% | 26.39% | +6.25 |
| 3 | Any-evidence hit | 25.00% | 33.33% | +8.33 |
| 3 | Complete evidence coverage | 16.67% | 20.83% | +4.17 |
| 5 | Macro evidence recall | 28.47% | 30.56% | +2.08 |
| 5 | Any-evidence hit | 33.33% | 37.50% | +4.17 |
| 5 | Complete evidence coverage | 25.00% | 25.00% | +0.00 |

Full-ranking MRR: **0.208245 → 0.246135** (delta +0.037890). This scores the first annotated evidence page only; it does not establish multi-page completeness.

- At k=5: any hit increases from **8/24 to 9/24**; complete coverage stays **6/24**.
- Top-five outcomes change from 16 misses / 2 partial / 6 complete to **15 misses / 3 partial / 6 complete**.
- All five multi-page questions still lack complete coverage at k=5.

## Paired changes and remaining failures

| k | Questions with increased recall | Decreased recall | Unchanged recall |
|---|---:|---:|---:|
| 1 | 1 | 0 | 23 |
| 3 | 2 | 0 | 22 |
| 5 | 1 | 0 | 23 |

**AMD 2015 D&A margin, question 03069:** cash-flow page 59 rises from rank 6 to rank 1. Operations page 55 rises from rank 64 to rank 25. This accounts for the entire Recall@5 gain (+0.5 / 24 = +2.08 percentage points), but the full annotated evidence set is still missing from the top five.

**Best Buy acquisition question 01077:** page 50 rises from rank 4 to rank 3. This accounts for the second question with increased Recall@3; its Recall@5 was already 1.

No question loses recall at the measured cutoffs. The full ranking is mixed: the first evidence page improves for 12 questions, regresses for five, and stays unchanged for seven. For example, PepsiCo geography question 01009 regresses from first-evidence rank 10 to 20; its page 3 moves from rank 35 to 228. Avoid describing this as an improvement for every question.

Derived-metric failures persist: AMD quick-ratio page 55 remains at rank 113, Best Buy gross-margin page 39 at 59, and Boeing gross-margin page 54 at 82. PepsiCo legal-proceedings page 25 remains at rank 133. These ranks, together with the earlier native-page inspection, are consistent with terminology and statement-localization gaps that function-word filtering alone cannot resolve. That causal interpretation remains a diagnostic inference.

## Per-question evidence ranks

Question IDs use the final FinanceBench numeric suffix. Entries are `zero-based page: one-based rank`; every annotated page is shown. R@5 is a fraction.

| Question | Report | Original page:ranks | Stopwords page:ranks | R@5 original → stopwords |
|---|---|---|---|---|
| 03069 | AMD_2015_10K | 55:64, 59:6 | 55:25, 59:1 | 0.000 → 0.500 |
| 00222 | AMD_2022_10K | 55:120 | 55:113 | 0.000 → 0.000 |
| 00995 | AMD_2022_10K | 3:7 | 3:8 | 0.000 → 0.000 |
| 01198 | AMD_2022_10K | 42:9 | 42:7 | 0.000 → 0.000 |
| 00917 | AMD_2022_10K | 42:7 | 42:6 | 0.000 → 0.000 |
| 01279 | AMD_2022_10K | 57:4 | 57:4 | 1.000 → 1.000 |
| 00563 | AMD_2022_10K | 47:1 | 47:1 | 1.000 → 1.000 |
| 00757 | AMD_2022_10K | 11:57 | 11:51 | 0.000 → 0.000 |
| 04417 | BESTBUY_2019_10K | 51:16 | 51:13 | 0.000 → 0.000 |
| 00685 | BESTBUY_2023_10K | 39:68 | 39:59 | 0.000 → 0.000 |
| 01077 | BESTBUY_2023_10K | 50:4 | 50:3 | 1.000 → 1.000 |
| 01275 | BESTBUY_2023_10K | 41:2 | 41:2 | 1.000 → 1.000 |
| 00517 | BOEING_2022_10K | 61:120 | 61:97 | 0.000 → 0.000 |
| 01091 | BOEING_2022_10K | 112:14 | 112:20 | 0.000 → 0.000 |
| 00678 | BOEING_2022_10K | 54:159 | 54:82 | 0.000 → 0.000 |
| 01290 | BOEING_2022_10K | 7:50, 9:3, 13:148 | 7:39, 9:3, 13:161 | 0.333 → 0.333 |
| 00464 | BOEING_2022_10K | 7:28 | 7:31 | 0.000 → 0.000 |
| 00494 | BOEING_2022_10K | 8:3 | 8:3 | 1.000 → 1.000 |
| 00585 | BOEING_2022_10K | 54:37 | 54:30 | 0.000 → 0.000 |
| 01009 | PEPSICO_2022_10K | 3:35, 4:10 | 3:228, 4:20 | 0.000 → 0.000 |
| 00735 | PEPSICO_2022_10K | 25:179 | 25:133 | 0.000 → 0.000 |
| 01328 | PEPSICO_2022_10K | 77:3 | 77:3 | 1.000 → 1.000 |
| 03620 | PEPSICO_2022_10K | 61:18, 63:1 | 61:17, 63:1 | 0.500 → 0.500 |
| 04481 | PEPSICO_2022_10K | 61:38, 63:13 | 61:33, 63:14 | 0.000 → 0.000 |

## Verification and provenance

The five uploaded files were read directly. Four output files match their manifest SHA-256 checksums and byte sizes. The comparison references the exact original baseline manifest and recorded input hashes. The frozen annotation checksum matches the original pilot task file. All 24 retrieval-query records contain exactly `task_id`, `doc_id`, and `question`, and exactly match the original question projection. Answers, justifications, evidence text, and evidence page labels do not appear as additional retrieval fields.

All prediction records match the comparison run, question and report identity; every report page occurs exactly once in each ranking. Scores are finite and nonnegative, ordered by descending score and ascending zero-based page ID for ties. Reproduced original rankings and scores match the supplied original predictions within 1e-12 relative/absolute tolerance. Original metrics match the earlier verified baseline. All per-question, aggregate, MRR, and delta values were independently recalculated from the frozen evidence page IDs without calling the pipeline evaluator.

Recorded repository revision is `776440c7b98ac40653189d6fff0dec5023583d57`, with local changes. The recorded package-source SHA-256 `d98faa5b16607e9f44a210f49e018d9fa527161710370d48ed99a13bde845778` matches the delivered implementation after Windows CRLF conversion. Runtime: Python 3.13.7, pypdf 6.19.0, Windows 11. The revision alone is insufficient provenance because the checkout is dirty; the matching package-source digest identifies the executed Python implementation.

The full `native_pages.jsonl` cache and PDFs were not uploaded for this review. Their checksums and full-cohort validation are recorded by the completed runner; variant BM25 scores were not independently recalculated from the entire cache here. This does not prevent independent verification of the supplied rankings’ evidence metrics.

## Timing and interpretation

Recorded comparison wall time: 0.968 s. Indexing: original 0.258 s, stopwords 0.261 s. Total query time across 24 questions: original 0.0328 s, stopwords 0.0161 s. These are a single cached-text run, with fixed execution order; they are not repeated latency, energy, or end-to-end extraction measurements. The original extraction cost remains shared ingestion cost.

This is a development ablation designed after inspecting labeled pilot failures. It does not establish statistical significance, answer correctness, OCR accuracy, or generalization to unseen companies/documents. Native text remains an unverified extraction reference. Preserve both original and stopword conditions.

The next proposed retrieval experiment should address question wording and financial-statement localization under the same full-report candidate scope. Define its question-only transformation or source-derived section policy before execution, retain both baselines, and score labels only afterward. The diagnostic evidence pages must not become a retrieval whitelist or a memory source. Keep OCR and answer-generation outcomes pending until those stages actually run.

## Windows: view a compact result

Use parsed objects to avoid printing the large per-question JSON:

```powershell
$m = Get-Content "$comparisonDir\comparison_metrics.json" -Raw | ConvertFrom-Json
$m.baseline.at_k."5"
$m.stopwords.at_k."5"
$m.delta_at_k."5"
$m.baseline.mrr_full_ranking
$m.stopwords.mrr_full_ranking
```

The five supplied comparison files are sufficient for this review. No pasted console transcript or additional copy of the original retrieval metrics is required; the original run artifacts were already available.
