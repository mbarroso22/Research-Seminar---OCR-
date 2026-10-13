# Source-derived section context against frozen expansion v1

Implementation date: 2026-10-12, continuing from pushed `dae9897`.
The researcher supplied the completed Windows run on 2026-10-12 (2026-10-13 UTC).
Read [the verified results](SECTION_CONTEXT_RESULTS.md). Tests and the original
source-span smoke checks validate implementation; their outcomes are separate
from the now-verified real pilot retrieval measurements.

## Single structural change

The [native-cache review](NATIVE_CACHE_DIAGNOSTIC.md) showed multiple local headings
per page, short continuation spans, statement titles outside an explicit Item 8
interval, and appended exhibits. This development condition uses those structural
patterns without a company/page lookup table, gold-page roles, answers or reviewed
operand values in its implementation.

| Component | Frozen expansion v1 | Section condition |
|---|---|---|
| Candidates | Every physical page in the specified report | Identical, including blank-native pages and attachments |
| Body index | Fixed stopword BM25 | Same in-memory body index and statistics |
| Query | Original question plus expansion v1 | Identical minimal expanded query |
| Additional field | None | Source-derived headings, capped at 64 lexical tokens/page |
| Page score | Body BM25 score | Body score + 0.25 × heading BM25 score |
| Ties | Score descending, zero-based page ascending | Same rule |
| Evaluation | Frozen annotations, k=1,3,5 | Same labels/cutoffs, after outputs are saved |

The separate heading index has its own report-wide DF, page lengths and average
length, including all report pages in N. It uses the same stopword tokenizer,
k1=1.2, b=0.75, positive IDF and binary question frequency. No heading concatenation
changes body DF or length normalization. Local headings already present in body
text receive additional weight through this field; that is a ranking choice, not
new evidence. The fixed 0.25 is an initial development choice, not a tuned optimum.
There is no weight search during execution.

Policy: `source-local-headings-v1`, SHA-256
`159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e`,
serialized in `configs/section_context_v1.json`. The JSON is a test/documentation
snapshot, not loaded to alter runtime configuration. Runtime records its policy
and code provenance. Later rule/cap/weight changes need a separately versioned
development condition. Expansion-v1 policy SHA-256 remains
`80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3`.

## Exact source policy

Construction accepts only `SourcePage(doc_id,page_index,raw_text)` objects, one
whole report in contiguous physical order. It has no question/task argument. All
12 reports receive context records, including six without questions; ranking/indexing
runs for reports with questions. No review document or correction memory is loaded.

1. Read raw lines with Unicode character offsets. Ignore exact case-insensitive
   Table of Contents/Contents navigation lines and standalone integer footers for
   heading detection/opening content. Retain all original text in body BM25.
2. A page with at least six lines matching the fixed terminal-page-reference pattern
   is a contents listing: clear continuation and emit no headings on it. A lone
   navigation prefix does not establish a contents listing.
3. Detect explicit Item headings, consolidated statement/balance-sheet titles, Note
   headings and Risks Related to headings using the snapshot's exact patterns.
   Generic titles have 2–12 words, <=120 characters, only letters/spaces/hyphens/
   apostrophes/ampersands, and title-case/all-caps words with recorded function-word
   exceptions. Numeric table rows and prose cross-references fail that title rule.
4. Weak sentence headings beginning We depend/We conduct/We derive/Changes in levels of
   may span at most two consecutive raw lines. A joined second line starts lowercase;
   the candidate ends with a period. All candidates have <=240 normalized characters
   and <=32 content tokens. Other candidates are ignored rather than assigned topics.
   Multi-line general titles are not reconstructed; sentence cues can confuse prose
   with headings, and a short contents list can escape the six-reference threshold.
5. Record exact observed raw spans and local scopes, ending at the next heading/reset
   or page end. Pointers use zero-based raw Unicode character offsets [start,end),
   not PDF geometry, bytes, normalized-search offsets or printed page numbers.
6. The last **locally observed** heading may carry once to the next page's opening,
   ending at its first local heading/reset. Inherited headings never propagate onward.
   Blank or navigation/footer-only pages clear state. A heading before the final reset
   on a page cannot be carried to the next page.
7. Reset at exact Signatures/Index to Exhibits/Exhibit Index lines, standalone Exhibit
   number lines within the first three meaningful lines, and a filing-cover United
   States line followed by Securities and Exchange Commission. Subsequent exhibit
   headings may establish fresh local context. Every page remains a candidate.
8. Assemble each field in scope order: opening inherited entry first, then local
   headings. Include each normalized casefold heading string once per page. Cap at
   **64 frozen-stopword lexical tokens**; skip an entire heading that would exceed
   the cap, log its rejection, and consider later headings. Do not truncate titles.

Observed headings are source spans; inherited scopes are weak inferences. Ranking
stays page-level: several local spans share one bounded heading field. This is not
span retrieval or verified semantic segmentation. No year/currency/unit is inferred
or carried as metadata; table-local source details remain authoritative for a later
extractor. Titles may contain observed item/note numbers. Adjacency, query cleanup,
operand reranking, model calls, answer generation and ledger retention are excluded
from this single structural change.

## Inputs, acceptance and costs

Supply the original **complete native run** and its completed **frozen expansion
run**. The separate old stopword directory is unnecessary: the expansion artifacts
already contain its control predictions/metrics. Both earlier runners stay unchanged.

The runner checks manifests/lineage, frozen task SHA, complete cohort, source hashes,
engine/text normalization, page accounting/statuses, query allowlists, fixed policy
and required artifact hashes/sizes. Original-native and expansion-run original
rankings both reproduce. Stopword and expanded rankings reproduce against the
unchanged body index. Expanded queries/audits reproduce. Scores use relative and
absolute tolerance 1e-12; full page order must match exactly.

All four full ranking files, original/expanded queries, expansion audit, page context
and context summary are saved before labels are parsed. Input hashes are rechecked,
then only task_id/doc_id/evidence_pages are loaded for offline scoring. Previous
metrics are read at that stage; all three control metrics must reproduce. Answers,
justifications and evidence snippets never enter context or retrieval.

Use a fresh output directory outside Git and existing runs. Preflight failure may
leave no directory; later failure records status failed/interrupted. Such outputs
are unaccepted even if predictions exist. No resume or output reuse is supported.

Primary effect: section context minus frozen expansion v1. Report Recall@5, any-hit
and complete coverage separately with counts and paired questions; k=1/3 and full
MRR remain diagnostics. The five-question multi-page subgroup is selected **offline**
after rankings are saved. No-match and zero-score ties follow the existing policy.
Page coverage is not answer correctness. This remains a labeled development pilot.

The manifest records all-report context construction, original/body/heading indexing,
per-condition query totals, new wall time, output sizes and heading-token counts.
Section query time includes body ranking, heading ranking and fusion. Historical
control reproduction is validation overhead; original PDF extraction is prior shared
ingestion. Context/index storage grows with documents: this is condition B, not a
bounded condition-C ledger. A single fixed-order run is not a latency/energy benchmark.

The heading cap uses lexical tokens, not an extractor tokenizer. Top-five scoring
does not enforce the proposed 4,096-model-token answer budget; no extractor is called.
Later context packing must account for headings/evidence within that separate budget.

## Apply and test in PowerShell

Download `section-context.patch` to Downloads. Use the existing .venv; no new
dependency, WSL or GPU installation is required. Preserve any local edits.

```powershell
Set-Location "$env:USERPROFILE\Downloads\Research-Seminar-OCR-current"
git status --short
git log -1 --oneline
if ((git rev-parse --short=7 HEAD) -ne "dae9897") {
    throw "Patch instructions start at dae9897. Preserve later commits/local edits."
}
$patchFile = "$env:USERPROFILE\Downloads\section-context.patch"
git apply --check $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; do not force or discard local changes." }
git apply $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }
$python = ".\.venv\Scripts\python.exe"
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; do not run the comparison." }
& $python -m finocr.cli compare-section-context --help
if ($LASTEXITCODE -ne 0) { throw "CLI check failed." }
```

Expected suite: **103 tests** (83 prior + 20 new). New checks cover offsets/scopes,
one-page continuation/no future-page leakage, resets, contents/cross-references,
complete-heading caps/deduplication, variable/label exclusion, an independent score
formula, unchanged body statistics, full-cohort/blank/attachment coverage, control
reproduction, tamper/metric rejection, immutable inputs, failed runs, fingerprints
and CLI paths. Source-only smoke checks confirm reviewed statement/risk/list offsets
and both long-report exhibit starts without any new corpus ranking/metric. PowerShell
is unavailable in the assistant environment; Python/CLI tests run here.

## Run the new comparison

The helper selects the frozen expansion directory by internal run ID and creates
a unique new output directory:

```powershell
& .\scripts\run_section_context.ps1
```

If that folder was moved/renamed, select its existing path explicitly:

```powershell
$expansionDir = Read-Host "Full path to the existing expansion-v1 run directory"
& .\scripts\run_section_context.ps1 -ExpansionDir $expansionDir
```

For a moved task file, add `-TasksPath` pointing to its unchanged copy. The helper
verifies native run `20261008T051510Z-7b1970c7f4e8` and expansion reference
`20261009T020622Z-76a16239e13d`. The run folder suffix need not equal the internal ID.

Alternatively, these complete direct CLI commands create `$comparisonDir` for
inspection without executing a .ps1 file:

```powershell
$dataRoot = "$env:USERPROFILE\financial-ocr-data"
$nativeRoot = Join-Path $dataRoot "derived\native"
$baselineDir = Join-Path $nativeRoot "native-bm25-20261008T051510Z-7fcc394d"
$expansionRunId = "20261009T020622Z-76a16239e13d"
$expansionRuns = @(Get-ChildItem -LiteralPath $nativeRoot -Directory -Filter "query-expansion-*" | Where-Object {
    $candidatePath = Join-Path $_.FullName "run_manifest.json"
    if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
        try {
            $candidate = Get-Content -LiteralPath $candidatePath -Raw | ConvertFrom-Json
            $candidate.run_id -eq $expansionRunId -and $candidate.status -eq "complete"
        } catch { $false }
    } else { $false }
})
if ($expansionRuns.Count -ne 1) { throw "Expected one expansion run; locate its saved path if moved." }
$expansionDir = $expansionRuns[0].FullName
$tasks = Join-Path $dataRoot "audits\financebench_phase0_sector_fixed\manifests\pilot_tasks.jsonl"
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$comparisonDir = Join-Path $nativeRoot "section-context-$stamp-$suffix"
& $python -m finocr.cli compare-section-context `
    --baseline-dir $baselineDir `
    --expansion-dir $expansionDir `
    --tasks $tasks `
    --output-dir $comparisonDir `
    --repository-root .
$comparisonExit = $LASTEXITCODE
Write-Host "Run directory: $comparisonDir"
Write-Host "Exit code: $comparisonExit"
if ($comparisonExit -ne 0) { throw "Comparison failed; inspect any new run manifest." }
```

Choose one run method. Do not rerun old conditions or re-extract PDFs. If using
the helper, set `$comparisonDir` to its printed directory before the next commands.

## Inspect and return outputs

```powershell
$manifest = Get-Content -LiteralPath "$comparisonDir\run_manifest.json" -Raw | ConvertFrom-Json
$manifest.status
$manifest.baseline_reproduced
$manifest.stopword_baseline_reproduced
$manifest.expansion_control_reproduced
$metrics = Get-Content -LiteralPath "$comparisonDir\comparison_metrics.json" -Raw | ConvertFrom-Json
$metrics.question_expansion.at_k."5"
$metrics.section_context.at_k."5"
$metrics.delta_at_k."5"
$metrics.multi_page.question_expansion.at_k."5"
$metrics.multi_page.section_context.at_k."5"
$metrics.section_context.mrr_full_ranking
```

Accept only status complete with all three reproduction flags true. Return these
**11 files from the new directory**, optionally zipped together:

1. run_manifest.json
2. comparison_metrics.json
3. section_predictions.jsonl
4. expanded_predictions.jsonl
5. stopword_predictions.jsonl
6. baseline_reproduced_predictions.jsonl
7. retrieval_queries.jsonl
8. expanded_retrieval_queries.jsonl
9. query_expansion_audit.jsonl
10. section_context.jsonl
11. section_context_summary.json

No PDFs or native-cache re-upload is needed. Keep these run artifacts unchanged.
Section predictions record total/body/heading/weighted-heading scores for every
candidate. Context exposes source pointers, observed/inherited modes, scope ends,
resets, capped tokens and rejections. Its summary records structural counts, token
totals and policy. These files support verification after execution; a terminal
completion message alone does not establish a measured structural effect.

To package the new directory after a successful run:

```powershell
$archive = Join-Path "$env:USERPROFILE\Downloads" ("section-context-results-" + $manifest.run_id + ".zip")
if (Test-Path -LiteralPath $archive) { throw "Archive already exists; preserve it or choose a fresh filename." }
Compress-Archive -Path (Join-Path $comparisonDir "*") -DestinationPath $archive
Start-Process explorer.exe -ArgumentList ('/select,"{0}"' -f $archive)
```
