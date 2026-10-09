# Native retrieval diagnostic and stopword comparison

2026-10-08. The original Windows native-text/BM25 run completed: 12 reports,
2,620 pages, 24 questions, zero extraction failures, seven empty-native-text pages.
Its verified Recall@5 is 28.47%, any-evidence Hit@5 is 8/24, and all-evidence
coverage@5 is 6/24. All five multipage questions missed complete coverage at k=5.
These remain the frozen original results. No new retrieval condition has been run
on the corpus in this continuation.

## Diagnostic scope and evidence

The researcher supplied `native_diagnostic_pages.jsonl`: 25 label-selected native
page records from the six annotated reports, including missed evidence and competing
high-ranked pages. All rows match the original run ID, zero-based page IDs, PDF hashes,
engine/version, character counts, normalization, and successful-extraction status.
This is offline error inspection, not an unbiased sample or a retrieval benchmark.

Relevant quantities and line items are visible on the inspected evidence pages:

| Report / question | Zero-based page(s) and source observations | Original evidence rank(s) |
|---|---|---:|
| AMD 2015 D&A margin | 55: net revenue 3,991; 59: depreciation/amortization 167 | 64, 6 |
| AMD 2022 quick ratio | 55: cash 4,835; short-term investments 1,020; receivables 4,126; current liabilities 6,369 | 120 |
| Best Buy 2019 inventory | 51: merchandise inventories 5,409, with 2019/2018 columns | 16 |
| Best Buy 2023 gross margin | 39: gross profit and revenue with three year columns | 68 |
| Boeing 2022 gross margin | 54: total revenues and costs, with year columns | 159 |
| PepsiCo 2022 legal matters | 25: Item 3 Legal Proceedings and management's material-effect statement | 179 |
| PepsiCo 2022 EBITDA less capex | 61: operating profit 11,512; 63: D&A 2,763 and capital spending (5,207) | 18, 1 |

These are operand/content visibility checks, not answer-generation accuracy or complete
PDF-to-text verification. Currency units/year headers remain visible in these tables;
no source images were supplied for visual confirmation of every glyph or reading order.

## Findings and their limits

1. **Instruction and function-word overlap can favor unrelated pages.** The long AMD
   D&A question includes role instructions about an analyst losing internet access.
   Pages 191 and 202 are equity-award/privacy/tax exhibits rather than the relevant
   statement tables. They match such query tokens as `access`, `details`, `providers`,
   `equity`, `you`, `if`, and `the`; they rank second and fourth. This is observed
   lexical overlap, not a measured attribution of each token's score contribution.
2. **Derived financial concepts may not be named in the source table.** AMD's balance
   sheet contains the needed line items but none of `quick`, `ratio`, or `liquidity`.
   Its overlap with the original question is only `and` and `to`. Boeing's operations
   page does not contain `gross` or `margin`. Removing common words cannot create
   missing metric terminology or perform the calculation.
3. **Vocabulary differs.** PepsiCo's source uses legal proceedings, litigation, claims,
   and material adverse effect; the question uses materially important legal battles.
   This suggests a semantic/section-routing limitation of exact lexical matching.
   The observed page is not empty and its legal section text is present.
4. **Two-digit fiscal-year wording is not normalized.** Current tokenization gives
   `FY22 -> ['fy', '22']`, while `FY2022 -> ['fy', '2022']`. Thus FY2022 already has
   a four-digit year token; FY22 does not. AMD's cover page includes a February 22
   date, illustrating that matching `22` need not mean fiscal year 2022.
5. **Some native text is visibly damaged.** Best Buy 2019 has broken words, merged
   lines, and awkward table ordering; the inventory label/value remain visible.
   Presence of native text is not proof of clean transcription. OCR/parser comparisons
   remain relevant, but this diagnostic does not establish their relative quality.
6. **Required statements can be separated in the ranking.** PepsiCo's cash-flow page
   ranks first while its income page ranks eighteenth. Broad cash-flow narrative pages
   outrank the second operand source. Any-hit and complete-evidence coverage therefore
   address different failures.

The diagnostic supports investigating retrieval representation/query handling. It does
not show that installing OCR will resolve the misses, that all native text is accurate,
or that a bounded memory ledger is already the needed solution. Section context,
semantic retrieval, year normalization, and table-aware extraction are later separately
identified interventions. Do not delete exhibits or pick pages from gold labels to make
an end-to-end retrieval score better.

## Implemented next experiment: stopword-only ablation

`finocr compare-stopwords` compares original BM25 to the same algorithm with a fixed,
self-contained English function-word list removed from both page and question tokens.
The exact sorted list, version, and checksum are saved. It was frozen after this
development diagnostic, so any gains are development findings, not held-out evidence.

Financial terms, company names, numbers, units, and negation (`not`, `no`, `without`)
remain. Years, stemming, query wording, IDF formula, k1=1.2, b=0.75, candidate pages,
tie policy, and k=1,3,5 remain unchanged. Term frequencies, document lengths, and IDF
are recomputed from the filtered token representation. No answer-derived keywords,
hand-picked report sections, dense model, OCR model, or memory component are added.

This isolates common function-word removal. Content words from role instructions
(`analyst`, `access`, etc.) are retained, so this experiment is not a complete query
cleaning system. It may improve, leave unchanged, or worsen retrieval. No improvement
is asserted before a real run.

The runner verifies the full cached native-page, sanitized-query, extraction-summary,
and original-prediction files against the original run manifest. It checks complete
physical-page coverage and reproduces every original page rank and score (1e-12
relative/absolute score tolerance). A partial diagnostic export is rejected. New outputs
are accepted only if the original rankings reproduce. Original files remain untouched.

Both prediction files are saved before the original task annotations are parsed for
offline evaluation. Only `task_id`, `doc_id`, and `question` enter retrieval. This
preserves the existing leakage boundary and zero-based page IDs. A new run directory
is required. Native text is reused; the original 88.41-second extraction-stage cost
still belongs to shared ingestion when discussing end-to-end cost.

61 local fixture tests passed, including the unchanged original 54 tests, full-scope
reproduction, label-loading order, financial token/negation retention, cache integrity,
rejection of incomplete exports, reproduction failure, and actual CLI artifacts.
Windows execution and corpus results for this new condition remain pending.

## Windows commands

Download `native-stopword-comparison.patch` to Downloads. Apply it to the repository
where `native-bm25-baseline.patch` has already been applied. This is an incremental
patch; do not apply it to an unpatched 5cf2842 checkout or reapply the original patch.

```powershell
Set-Location "$env:USERPROFILE\Downloads\Research-Seminar-OCR-current"
git status --short
$patchFile = "$env:USERPROFILE\Downloads\native-stopword-comparison.patch"
git apply --check $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; retain your edits and share the output." }
git apply $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }

$python = ".\.venv\Scripts\python.exe"
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; resolve them before running." }

$baselineDir = "$env:USERPROFILE\financial-ocr-data\derived\native\native-bm25-20261008T051510Z-7fcc394d"
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$comparisonDir = "$env:USERPROFILE\financial-ocr-data\derived\native\stopwords-$stamp-$suffix"
& $python -m finocr.cli compare-stopwords `
  --baseline-dir $baselineDir `
  --output-dir $comparisonDir `
  --repository-root .
$comparisonExit = $LASTEXITCODE
Write-Host "Exit code: $comparisonExit"
Write-Host "Output directory: $comparisonDir"
```

These commands invoke Python directly, so downloaded PowerShell script-signature
restrictions do not apply. No execution-policy changes, re-extraction, new dependencies,
WSL, model download, or GPU setup are required. The default task path comes from the
original run manifest; if the data moved, pass `--tasks` with the exact unchanged pilot
task file. A changed task checksum is rejected. Use a new output directory for retries.

Return the command summary and these new comparison files:

- `run_manifest.json`;
- `comparison_metrics.json`;
- `stopword_predictions.jsonl`;
- `baseline_reproduced_predictions.jsonl`.

Keep the original run's 28.47% Recall@5 and other metrics as condition N. Compare paired
per-question outcomes, including regressions and no-match counts, after receiving the
real comparison files. Do not replace the original result with whichever variant scores
better on this exposed development pilot.
