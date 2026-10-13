# Final planned heading-format ablation: note coverage

Starting checkpoint: pushed `7ebb8f5`. Implementation, source validation and the
user's local run are complete. Read [the verified results and baseline recommendation](NOTE_FORMAT_RESULTS.md).
Expansion v1 remains the frozen development control and recommended baseline
for matched native/OCR retrieval at k=5. This is the final planned heading-format
ablation; retain the note-format comparator and move to rendering/OCR evaluation.

## Conditions and fixed components

| Condition / metrics key | Role | Change |
|---|---|---|
| E / `question_expansion` | Frozen expansion v1 development control | None |
| S1 / `section_context` | Saved section v1 comparator | None; reproduce source contexts, full rankings and score components |
| S2 / `note_formats` | New note-format condition | En-dash Note titles and guarded bare numbered notes |

S2 minus S1 isolates the note-format recognition bundle. S2 minus E measures its
combined structural effect. The two syntax additions are one ablation; it does
not separate their individual retrieval contributions. Original native and
stopword controls also reproduce. Existing commands and policy snapshots remain
available with their original behavior.

Hold question expansion v1 (SHA `80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3`),
stopwords, tokenizer, NFKC search normalization, no stemming, BM25 k1=1.2/b=0.75,
binary query frequency, 0.25 heading weight, 64 heading tokens/page, complete-heading
cap/duplicate rules, local scopes, one-page non-chaining continuation, resets and
tie ordering fixed. All physical pages remain candidates, including blanks and
attachments. Physical PDF page IDs are zero-based; ranking positions are one-based.
Each S2 body score must equal its E body score exactly.

New heading boundaries naturally change local spans, the last heading eligible
for continuation, cap competition, heading-field DF and average length. These
are consequences of detection; body text/index and scoring rules do not change.
Generic title, risk and statement-prefix rules are unchanged, including known
table-label and statement-prose false positives.

## Frozen source-only detector

The complete policy is `configs/note_formats_v1.json`. Its SHA is
`cbbc145937e12535a3db7243a28c9eebf0c5d20f14e42b85fe4e5bd4b9cebb2a`.
It embeds the unchanged section-v1 policy (SHA
`159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e`).

1. Add U+2013 **en dash** to the supported `Note N` forms. Existing colon, period,
   em dash and hyphen forms stay unchanged. Preserve raw Unicode text/offsets;
   no global punctuation rewriting or query changes. Reject page-reference lines
   and dense contents pages using the existing rules and candidate limits.
2. Recognize a bare `N. Title` only after an exact standalone source line
   `Notes to Consolidated Financial Statements`, optionally `(continued)`.
   Matching is case-insensitive. A longer prose mention cannot enable eligibility.
3. Start a bare-note chain only at **1 on the same physical page as that parent**.
   Then accept only the next integer in source order (1..99, no leading zero).
   Gaps, repeats and backward numbers are rejected and logged without advancing
   the chain. Repeated exact parents preserve an active chain. This is deliberately
   conservative: wrapped/different numbering forms do not repair the chain.
4. A bare title has 1..12 words and at most 120 characters, with the frozen
   title-case/all-caps letter/hyphen/apostrophe/ampersand grammar. One-word titles
   are permitted; numbers, terminal punctuation, prose and page references are
   rejected. Frozen candidate limits (32 stopword tokens / 240 normalized
   characters) apply before a heading is accepted.
5. Clear recognition eligibility at a new report, every existing v1 reset,
   blank/navigation/footer-only pages and an **observed** Item boundary. Keep
   the existing contents detection, filing covers, signatures and exhibit resets.

The region state contains only parent page and last bare-note number. It permits
recognition across notes pages; it does not carry parent heading text or financial
variables across those pages. Ordinary heading text still carries once, to the
next physical page only. No company/page/topic whitelist, annotation lookup,
financial-value ledger or future-page lookahead is used.

Every bare-pattern candidate has a raw source pointer and accepted/rejected reason
in `note_context.jsonl` under `note_detection`. Parent/reset events and before/after
recognition state are also saved. Heading admission by the token cap is separate
from detection acceptance; a detected note can be rejected by the field cap.

This syntax cannot prove that every sequential title-shaped list in a notes region
is a financial note. Eligibility plus strict sequence rejects many ambiguous
cases but sacrifices coverage. Missing first notes, unsupported titles, sequence
gaps and existing v1 false contents resets can prevent later bare coverage. These
are declared limits, not reasons to change the rule after viewing task outcomes.

## Pre-run validation scope

The Python suite has 123 passing tests: the previous 103 plus 20 note-format tests.
It exercises real small PDF/cache/control fixtures, raw Unicode/CRLF spans,
parent/prose distinction, first-note/sequential gates, contents/numeric/list
negatives, all reset classes, one-page continuation, full report candidates,
unannotated reports, body-score invariance, control/context/component tampering,
source mutation, label exclusion and the new CLI.

Source-only inspection of the uploaded cache reproduced all **2,620 saved S1
context records exactly**, without loading task annotations or ranking S2 queries.
The new detector recognizes Best Buy 2023 p50's `2. Acquisitions` at [1837,1854)
and `3. Restructuring` at [3369,3387); the former scope ends at 3369. It recognizes
Boeing 2022 p111's `Note 21 – Legal Proceedings` at [2122,2149), carries it only
over p112's opening [18,2429), and closes that span at the new Note 22 boundary.
These are source-format checks, **not retrieval results or heading precision/recall**.

Hard-negative review includes numbered grant/exhibit lists and certification prose
across AMD/Boeing/PepsiCo, contents references, financial table lines, and the Best
Buy parent prose mention. Known conservative misses remain: the unchanged dense
reference heuristic resets the Best Buy 2015 notes region at p74; several Best Buy
2019 notes use unsupported split numbering/title lines, preventing a sequential
chain beyond note 1. No contents or split-line cleanup is bundled into this run.
No pilot S2 ranking, score, accuracy, timing or gain has been reported here.
PowerShell is not installed in this validation environment; the helper is supplied
for the user's Windows execution, while Python/CLI fixtures have been executed.

## Exact PowerShell application and run

Download `note-format.patch` to Downloads. Start in the existing repository;
preserve any local results updates. The initial commit should be `7ebb8f5`.
If the patch check fails, stop and retain the diagnostic; do not reset local files.

```powershell
Set-Location "C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current"
git rev-parse --short HEAD
git status --short
$patchPath = Join-Path $env:USERPROFILE "Downloads\note-format.patch"
git apply --check $patchPath
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; preserve local changes and inspect the diagnostic." }
git apply $patchPath
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; do not accept a pilot run." }
& .\.venv\Scripts\python.exe -m finocr.cli compare-note-formats --help
if ($LASTEXITCODE -ne 0) { throw "New CLI is unavailable." }
& .\scripts\run_note_formats.ps1
```

The existing editable environment suffices; there are no new dependencies. The
helper selects the verified original native run, discovers saved expansion/S1
runs by **internal manifest run IDs**, and creates a unique `note-formats-*`
directory outside Git. It never overwrites any saved run. Expected IDs:

| Run | Internal manifest ID |
|---|---|
| Original native | `20261008T051510Z-7b1970c7f4e8` |
| Expansion v1 | `20261009T020622Z-76a16239e13d` |
| Section v1 | `20261013T010312Z-967cd9567b9c` |

Folder suffixes differ from internal IDs. If runs/tasks were moved, use explicit
paths (replace only folder locations, retain the files and their hashes):

```powershell
$dataRoot = "C:\Users\mbarroso\financial-ocr-data"
$nativeRoot = Join-Path $dataRoot "derived\native"
$nativeDir = Join-Path $nativeRoot "native-bm25-20261008T051510Z-7fcc394d"
$expansionDir = Join-Path $nativeRoot "query-expansion-20261009T020621Z-83ca9076"
$sectionDir = Join-Path $nativeRoot "section-context-20261013T010312Z-1a0d48a0"
$tasksPath = Join-Path $dataRoot "audits\financebench_phase0_sector_fixed\manifests\pilot_tasks.jsonl"
& .\scripts\run_note_formats.ps1 -DataRoot $dataRoot -BaselineDir $nativeDir `
    -ExpansionDir $expansionDir -SectionDir $sectionDir -TasksPath $tasksPath
```

Equivalent direct command, using the variables above and a new output directory:

```powershell
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$runDir = Join-Path $nativeRoot "note-formats-$stamp-$suffix"
& .\.venv\Scripts\python.exe -m finocr.cli compare-note-formats `
    --baseline-dir $nativeDir --expansion-dir $expansionDir --section-dir $sectionDir `
    --tasks $tasksPath --output-dir $runDir --repository-root (Get-Location).Path
if ($LASTEXITCODE -ne 0) { throw "Comparison failed; results are not accepted." }
```

Use **one** helper/direct invocation for the planned run. Successful execution
reports exit code 0, status `complete`, 12 documents, 2,620 pages, 24 questions,
`expansion_control_reproduced: true`, and `section_control_reproduced: true`.
The manifest also records original/stopword reproduction. Failed/interrupted
manifests are retained and do not establish accepted results. Re-run to a new
directory after resolving an actual failure; do not edit the saved controls.

## Artifacts and later verification

The new directory has 14 files: a manifest plus 13 hashed artifacts:

- Five full-ranking prediction files: original, stopwords, expansion, S1 and
  `note_predictions.jsonl` (S2). S1/S2 rows include body, heading and weighted scores.
- Three minimal query/audit files: `retrieval_queries.jsonl`,
  `expanded_retrieval_queries.jsonl`, `query_expansion_audit.jsonl`.
- Four all-report source files: `section_context.jsonl`, `section_context_summary.json`,
  `note_context.jsonl`, `note_context_summary.json`.
- `comparison_metrics.json`, evaluated offline only after all the files above
  are written and control predictions/context have reproduced.

Inputs and all saved artifacts are hash/size checked; native cache provenance,
task-file identity, cohort, control policies and run lineage must agree. S1 source
contexts/summary reproduce exactly. Every saved ranking and S1 score component
must reproduce within relative/absolute 1e-12 tolerance; zero ties/page sets must
match exactly. Rehash inputs before labels and before/after metrics to detect
mutation. Answers, justifications and evidence text are not retrieval fields;
evidence-page labels enter only the offline evaluator/paired review.

In `comparison_metrics.json`, historical `delta_at_k` and `delta_mrr_full_ranking`
still mean S1 minus E. **New comparisons** are under
`note_comparisons.section_context` (S2 minus S1) and
`note_comparisons.question_expansion` (S2 minus E). Each contains Recall/Hit/complete
coverage deltas at 1/3/5, MRR delta, paired gain/regression counts and per-question
gold-page ranks and multi-page subgroup deltas. Negative `rank_change` means improvement. `multi_page` contains
all three conditions for the five multi-page questions. Interpret MRR separately
from recovery of every required evidence page.

Upload the entire new output directory as a ZIP for verification. To zip the
directory printed by the helper, paste its exact path below:

```powershell
$runDir = "C:\Users\mbarroso\financial-ocr-data\derived\native\note-formats-PASTE-THE-PRINTED-SUFFIX"
$zipPath = "$runDir.zip"
if (Test-Path -LiteralPath $zipPath) { throw "ZIP already exists; choose a new ZIP path." }
Compress-Archive -Path (Join-Path $runDir "*") -DestinationPath $zipPath
Write-Host $zipPath
```

## Predeclared decision rules: freeze retrieval, then OCR

These rules were declared before local execution/artifact verification. The
verified recommendation is now in docs/NOTE_FORMAT_RESULTS.md. The following
text preserves the original decision criteria and transition plan.
After checking controls, source detection/scopes, per-question gains/regressions,
all five multi-page cases and costs, recommend **one** baseline and save its
policy hashes, source commit, control/run identities, candidate/query contracts,
k=1/3/5 metrics and known failure cases. Expansion v1 stays the development control.

Use macro evidence Recall@5 as primary, with Hit@5 and complete coverage as
decision checks. Favor expansion v1 when S2 only changes deeper ranks/MRR or
detects valid headings without improving evidence coverage. Consider S2 if it
produces useful paired Recall@5/complete-coverage gains with understood regressions
and a justified incremental cost; inspect company concentration and subgroup
behavior before making that recommendation. Include S1 in the comparison, but
its existing MRR-only improvement supplies no primary coverage advantage over E.
With 24 development questions, selection is exploratory, not held-out validation.
Avoid a post-result weight search or another heading-format repair round.

The transition follows roadmap phases 2–4:

1. Freeze the selected retrieval policy and the existing 12/2,620/24 cohort.
   Retain native outputs as the representation control. Record hardware/runtime
   feasibility before selecting/pinning the first standard OCR adapter; no OCR
   model is installed by this patch. If a structural baseline is chosen, apply
   its same text-only heading grammar to OCR text in the matched comparison;
   geometry-assisted detection would be a separate future condition.
2. Verify original PDF hashes and render pages sequentially with a pinned
   renderer. Start with the documented 200-DPI RGB proposal; inspect small
   figures/footnotes and a small 300-DPI comparison before freezing resolution.
   Save source PDF/page ID, image hash, dimensions, rotation, DPI and failures.
   Existing `render-pages` renders **evidence pages**, not the full-report cache;
   implement/validate the full-report rendering path before a retrieval study.
3. Smoke-test one OCR engine on representative pages and the 25 distinct
   annotated evidence pages as a clearly labeled **oracle evidence diagnostic**.
   Cache immutable raw text/boxes/confidence where available, versions/checkpoints,
   device, initialization/page timings and errors. Visually review numbers, signs,
   units/years and table reading order. Native text is not perfect transcription;
   CER/WER requires a manually verified subset rather than treating native text
   or evidence snippets as complete page ground truth.
4. OCR complete reports with resumable page accounting, then run the frozen
   retrieval method on matched OCR/native text with identical queries, PDFs,
   page candidates, k and labels. Keep failed/blank pages visible and preserve
   zero-based IDs. If full pilot inference is infeasible, use one complete short
   annotated report as a declared smoke milestone, retaining the larger cohort
   and avoiding full-pilot recall/throughput claims from evidence-only pages.
5. Review representation-driven retrieval/numeric failures and measure shared
   rendering/OCR cost separately from indexing/context/query cost. Proceed to
   fixed answer extraction/citation scoring only after this matched retrieval
   stage; memory/ledger, new matching rules and held-out company studies remain
   separate experiments. No energy or accuracy claim precedes measurement.
