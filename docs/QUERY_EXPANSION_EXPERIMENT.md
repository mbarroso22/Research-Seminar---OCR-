# Next development experiment: question-only financial-term expansion

Status: the researcher supplied a real Windows run, independently verified on
2026-10-08. Read `docs/QUERY_EXPANSION_RESULTS.md` for the results and limitations. This patch starts at pushed commit `3550ba2f352a9be216455275559fbf0c9bbc3a1e`.

## Why this experiment

The verified stopword-only run raised macro evidence Recall@5 from 28.47% to
30.56%, while complete evidence coverage stayed at 6/24. Its entire top-five gain
came from one additional page for AMD's two-page D&A question. Native-page inspection
showed that several missed statement pages contain relevant financial line items
but lack the question's metric name. The next hypothesis is that generic
question-derived financial search terms can improve localization of those pages.

This is a deliberately small retrieval ablation before OCR/context/model work.
It was designed after inspecting labeled development failures. Report it as
development-only, never as held-out validation or a memory contribution.

## Frozen comparison

| Condition | Page index | Question tokens |
|---|---|---|
| Original control | Original native BM25 | Original question |
| Stopword control | Fixed stopword native BM25 | Original question, fixed stopwords removed |
| Question expansion | The very same stopword index | Original question plus fixed financial terms, fixed stopwords removed |

The primary effect is **question expansion minus stopword control**. Comparison
with the original control is secondary; it combines the earlier stopword change
and the new expansion. Do not attribute that combined delta solely to expansion.

The runner requires the original complete native run and the completed stopword
comparison for that exact run. It validates recorded artifact hashes, frozen task
hash, question projection, configuration, source page records and coverage. It
recalculates original and stopword rankings and compares their full page order and
scores with the saved controls (relative/absolute tolerance 1e-12). It checks that
both control metrics reproduce. A mismatch rejects the new experiment.

All reports are validated, including reports without questions. All physical pages
within each questioned report remain candidates. Page IDs stay zero-based; blank
pages remain in the candidate set. BM25 k1, b, tokenizer, numeric/year handling,
binary query frequency, and deterministic tie policy remain fixed. The expanded
condition reuses the stopword index, including its original DF and page lengths.
It does not enrich page text, restrict pages, use headings, add adjacent pages,
rewrite role instructions, or generate answers.

Only the minimal `RetrievalQuery(task_id, doc_id, question)` reaches expansion and
ranking. Rules inspect question text only, never task IDs or report IDs. Labels,
answers, justifications, and evidence text are excluded. All three prediction
files and query/audit files are saved before the frozen annotations are parsed for
offline scoring. Previously saved metrics are read only at that scoring stage.

## Exact rule policy

`financial-question-terms-v1` is a fixed 12-rule list in
`src/finocr/retrieval/query_expansion.py`. These are lexical search cues, **not
accounting identities, operand selections, synonyms guaranteed to be equivalent,
or answer calculations**. For example, an EBITDA query receives operating-income
and depreciation/amortization vocabulary; this does not equate operating income
with EBITDA. Related statement terms can also introduce irrelevant matches.

Matching uses contiguous original question tokens before stopword removal, with
the existing case folding and normalization. Thus `acid-test ratio` matches
`acid test ratio`, and `D&A` matches `d a`. No stemming, substring matching, fiscal
year expansion, company-specific rules, recursive expansion, query-dependent
weights, model calls, or annotation-driven runtime changes are used.

All matching rules contribute. Added terms are filtered with the same stopword
list, deduplicated, exclude content tokens already present in the question, and
are sorted alphabetically. At most 32 distinct terms are appended; overflow keeps
the alphabetical first 32 and logs how many were discarded. Original wording,
years, numbers, signs, and negation remain in the question. An unmatched question
is unchanged. Binary BM25 query frequency prevents repeated terms from increasing
their query weight.

| Rule | Trigger phrases | Added vocabulary before removal of existing terms |
|---|---|---|
| quick_ratio | quick ratio; quick ratios; acid test ratio | cash equivalents short term investments marketable securities accounts receivable current liabilities |
| current_ratio | current ratio; current ratios | current assets liabilities |
| gross_margin | gross margin; gross margins; gross profit margin; gross profit margins | gross profit revenue revenues net sales cost goods sold |
| operating_margin | operating margin; operating margins; operating profit margin | operating income profit revenue revenues net sales |
| net_margin | net margin; net margins; net profit margin; net income margin | net income earnings revenue revenues sales |
| ebitda | ebitda | operating income profit depreciation amortization |
| ebit | ebit | operating income profit |
| capital_expenditure | capex; capital expenditure; capital expenditures; capital spending | capital expenditures spending purchases property plant equipment |
| depreciation_amortization | d a; depreciation and amortization; depreciation amortization | depreciation amortization cash flows |
| return_on_assets | return on assets; roa | net income total assets |
| return_on_equity | return on equity; roe | net income shareholders stockholders equity |
| debt_to_equity | debt to equity; debt equity | debt borrowings shareholders stockholders equity |

The complete serialized policy, version, and SHA-256 are recorded in the new run
manifest. Freeze this version for the first run; a later rule or cap change is a
new development experiment with its own version and new output directory. Do not
choose a winning policy using held-out labels. This rule list intentionally does
not address every failure type, such as legal/geographic prose or damaged words.

## Metrics and interpretation

Use the same 24 questions and k=1,3,5. Primary: macro evidence Recall@5. Report
any-evidence hit and all-evidence coverage separately, including raw counts.
Report Recall@1/@3 and full-ranking MRR as diagnostics. Compare paired questions,
including gains, regressions, unchanged questions, and multi-page completeness.
No-match queries remain in the denominator; ascending zero-score page ties can
hit labels by chance under the frozen policy.

Native extraction is a shared prior ingestion cost. The expanded condition shares
the stopword index; its additional index cost is zero because the exact same
in-memory index object is used. Record question-transformation time separately
from each condition's query time. Total new wall time includes input validation,
query transformation, reproduction, ranking, scoring, and output overhead. Do not
add all three control query costs and describe that as the expanded condition's
deployment cost. A single fixed-order run is not a repeated latency or energy
benchmark. No speed, accuracy, OCR, answer-correctness, or generalization claim is
established until the appropriate real measurements exist.

The 25 diagnostic pages cannot substitute for the full page cache. The runner
rejects incomplete caches and mismatched controls. OCR, final evidence packing,
answer generation, source-derived section context, and bounded memory remain later
stages. Neither the five-page retrieval cutoff nor these added query terms establish
the proposed 4,096-token extractor input budget; no extractor is invoked here.

## Windows: apply and test

Download `native-query-expansion.patch` into Downloads. From PowerShell, use your
current repository and existing environment. These commands invoke Python directly
and require no change to PowerShell script execution policy.

```powershell
Set-Location "$env:USERPROFILE\Downloads\Research-Seminar-OCR-current"
git status --short
git log -1 --oneline
# The starting commit should be 3550ba2; preserve any later unrelated edits.

$patchFile = "$env:USERPROFILE\Downloads\native-query-expansion.patch"
git apply --check $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; do not force it or discard local changes." }
git apply $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }

$python = ".\.venv\Scripts\python.exe"
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; do not run the experiment yet." }
& $python -m finocr.cli compare-query-expansion --help
if ($LASTEXITCODE -ne 0) { throw "CLI check failed." }
```

The expected local suite has 76 passing tests (61 prior plus 15 new). It includes
rule matching/boundaries, unchanged unmatched queries, numeric/negation retention,
both control reproductions, full candidate scope including blank/unannotated
reports, label isolation with changed labels, tamper/mismatch rejection, immutable
inputs, failed-run status, and CLI success/error paths. These synthetic fixture
checks are software validation, not pilot research results. The full-pilot Windows run has now been supplied and verified; the 76-test
count above describes the local fixture suite.

## Windows: locate the frozen stopword run and execute

The stopword output folder's GUID suffix can differ from the internal run ID.
Locate it by its manifest's exact verified run ID, then create a new output folder:

```powershell
$nativeRoot = "$env:USERPROFILE\financial-ocr-data\derived\native"
$baselineDir = Join-Path $nativeRoot "native-bm25-20261008T051510Z-7fcc394d"
$stopwordRunId = "20261009T012131Z-1e32aa99fc79"
$stopwordRuns = @(Get-ChildItem -LiteralPath $nativeRoot -Directory -Filter "stopwords-*" | Where-Object {
    $candidateManifestPath = Join-Path $_.FullName "run_manifest.json"
    if (Test-Path -LiteralPath $candidateManifestPath) {
        try {
            $candidateManifest = Get-Content -LiteralPath $candidateManifestPath -Raw | ConvertFrom-Json
            $candidateManifest.run_id -eq $stopwordRunId -and $candidateManifest.status -eq "complete"
        } catch { $false }
    } else { $false }
})
if ($stopwordRuns.Count -ne 1) { throw "Expected exactly one matching stopword run. Locate its saved folder and set stopwordDir explicitly." }
$stopwordDir = $stopwordRuns[0].FullName

$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$comparisonDir = Join-Path $nativeRoot "query-expansion-$stamp-$suffix"
& $python -m finocr.cli compare-query-expansion `
    --baseline-dir $baselineDir `
    --stopword-dir $stopwordDir `
    --output-dir $comparisonDir `
    --repository-root .
$comparisonExit = $LASTEXITCODE
Write-Host "Run directory: $comparisonDir"
Write-Host "Exit code: $comparisonExit"
if ($comparisonExit -ne 0) { throw "Comparison failed. Inspect the error and any new run manifest; do not treat outputs as accepted results." }
```

The original frozen task file path is taken from the baseline manifest. If you
moved that file, add `--tasks` with its current path; its SHA-256 must still match.
No PDFs need to be re-extracted, and no new dependency, GPU, or WSL is required.
Do not rerun either prior condition in its old output directory.

## Read a compact summary and return artifacts

```powershell
$m = Get-Content -LiteralPath "$comparisonDir\comparison_metrics.json" -Raw | ConvertFrom-Json
$m.baseline.at_k."5"
$m.stopwords.at_k."5"
$m.question_expansion.at_k."5"
$m.delta_at_k.stopwords."5"
$m.question_expansion.mrr_full_ranking
```

Upload these **eight files from the new comparison directory** for verification:

1. `run_manifest.json`
2. `comparison_metrics.json`
3. `expanded_predictions.jsonl`
4. `stopword_predictions.jsonl`
5. `baseline_reproduced_predictions.jsonl`
6. `retrieval_queries.jsonl`
7. `expanded_retrieval_queries.jsonl`
8. `query_expansion_audit.jsonl`

The manifest must have `status: complete`, `baseline_reproduced: true`, and
`stopword_baseline_reproduced: true`. It records provenance, both control identities,
input hashes, frozen policy, transformation count, timings, and output hashes/sizes.
Expanded query records still contain only the three allowed query fields; the
separate audit records matched rules, added terms, and token counts. Do not edit
these files after execution. Existing runs are left unchanged; retries use a new
directory. A pasted terminal transcript is optional and cannot replace these files.
