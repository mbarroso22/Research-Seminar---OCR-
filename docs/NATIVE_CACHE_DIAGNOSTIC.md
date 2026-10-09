# Full native-cache diagnostic before section context

Date: 2026-10-09. Starting checkpoint: pushed commit `b15a868`.

The supplied full native cache reproduces the user's existing original, stopword,
and expansion rankings. Exact term attribution confirms why PepsiCo's income
statement loses rank even as its score increases. Native source inspection also
shows why a single 10-K item label carried across pages is too coarse for the next
structural condition. **Section context is not implemented by this continuation.**

This follows [the five-question review](MULTIPAGE_REVIEW_AND_PIPELINE_TRACE.md).
That earlier review's unavailable-cache/native-page limitations are now resolved.
Its original artifact availability and Windows patch instructions remain historical.
No further cache upload or PDF re-extraction is needed for this diagnostic.

## Control and source identities

Expansion v1 remains the development control, policy SHA-256
`80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3`.
`EXPANSION_V1_CONTROL.json`, query expansion, stopwords, tokenizer, BM25 parameters,
candidate set and ties are unchanged. The README additions omitted when applying
the previous patch are reconciled as links/status text while preserving the pushed
verified results and commands.

The uploaded cache is byte-identical to the original run's recorded artifact:

| Check | Verified value |
|---|---|
| SHA-256 | `c6de36446465cc9bdc27dfbf1dde2bc24c5cdd7f6b52a57b0f03fd7358d03a52` |
| Bytes | 16,163,945 |
| Native run | `20261008T051510Z-7b1970c7f4e8` |
| Expansion reference run | `20261009T020622Z-76a16239e13d` |
| Coverage | 12 reports; 2,620 contiguous, unique, zero-based physical pages |
| Native-text statuses | 2,613 ok; 7 blank_native_text; 0 failed |
| Extraction | pypdf 6.19.0, plain; every page attempted |

For every record, the source hash, expected source hash, extraction summary source
hashes, run ID, engine/version, representation, page ID, status, raw character count,
and normalized search text were checked. Every per-report count, blank-page list,
and total raw character count matches the supplied extraction summary. Blank native
text does not establish that a PDF page is visually blank. The PDFs are not supplied
here: their hashes are cross-checked against recorded provenance, not rehashed from
the original PDFs. Native text remains an approximate source representation.

All seven expansion artifacts were verified against the expansion manifest. Query
and audit reproduction accepts only the three minimal fields task_id/doc_id/question.
The new diagnostic helper does not load tasks, answers, justifications, evidence
labels, review documents, or correction memory. It verifies the metrics artifact's
byte checksum without parsing its evaluation content.

## Ranking reproduction

The full candidate indexes are rebuilt from source cache text for the six reports
with questions. Cache validation still covers all 12 reports. Original queries rank
against the original and stopword indexes; the expanded queries rank against that
same stopword index. All saved question expansions/audits are also reproduced.

| Check | Result |
|---|---:|
| Questions | 24 |
| Conditions per question | 3 |
| Full rankings reproduced | 72 |
| Individual page scores checked | 15,717 |
| Maximum absolute score difference | 7.105427357601002e-15 |
| Acceptance threshold | 1e-12 absolute |
| Page-order differences | 0 |

This reproduces existing real execution outputs; it is not a new retrieval treatment,
an accuracy improvement, an answer-generation result, or a latency benchmark. The
previous whole-pilot expansion Recall@5=40.97% remains the development reference.
No new accuracy metric is claimed. Diagnostic page choices below only select rows
to inspect **after** full-report ranking; they never select retrieval candidates.

## Exact trace: PepsiCo 03620, EBITDA less capex

Report: `financebench:PEPSICO_2022_10K`. Its stopword index has **N=503**,
**124,621 total page tokens**, and **average page length=247.7554671968191**.
The query has 31 original distinct content terms and 39 after the eight additions.
Query frequency is binary; terms sum in sorted order. k1=1.2, b=0.75. Blank pages
would count in N/average length; this report has no blank-native pages.

For term t on page p:

```text
idf(t) = log1p((N - df(t) + 0.5) / (df(t) + 0.5))
norm(p) = 1 - b + b * page_length(p) / average_page_length
contribution = idf(t) * tf(p,t) * (k1 + 1) / (tf(p,t) + k1 * norm(p))
```

The eight added terms are capital, equipment, expenditures, plant, profit, property,
purchases, spending. The following values are computed from the full 503-page
index, not estimated from isolated pages. Scores below are rounded to six decimals;
the JSON diagnostic retains all terms, DF/TF/IDF and unrounded contributions.

| Added term | Report DF | IDF | p61 | p63 | p46 | p53 | p76 | p54 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| capital | 49 | 2.320604 | 0 | 2.252739 | 3.883633 | 3.921027 | 2.882449 | 3.002532 |
| equipment | 30 | 2.804850 | 0 | 2.722824 | 2.137064 | 2.794493 | 3.483937 | 2.570382 |
| expenditures | 13 | 3.619887 | 0 | 0 | 2.758054 | 0 | 0 | 3.317287 |
| plant | 26 | 2.945432 | 0 | 2.859295 | 2.244175 | 2.934556 | 3.658555 | 2.699212 |
| profit | 24 | 3.023903 | 4.635432 | 0 | 2.303964 | 0 | 2.616704 | 0 |
| property | 37 | 2.598235 | 0 | 2.522252 | 1.979641 | 2.588641 | 3.227299 | 2.381039 |
| purchases | 6 | 4.350774 | 0 | 5.860928 | 0 | 0 | 0 | 0 |
| spending | 13 | 3.619887 | 0 | 3.514026 | 4.888283 | 3.606520 | 0 | 3.317287 |

| Page | Stopword length | Norm | Base score | Added score | Expanded score | Stopword → expansion rank |
|---|---:|---:|---:|---:|---:|---|
| 61 | 157 | 0.725267 | 18.811897 | 4.635432 | 23.447328 | 17 → 23 |
| 63 | 266 | 1.055229 | 34.389094 | 19.732065 | 54.121159 | 1 → 1 |
| 46 | 437 | 1.572877 | 30.744460 | 20.194814 | 50.939273 | 2 → 2 |
| 53 | 250 | 1.006795 | 29.684761 | 15.845237 | 45.529998 | 3 → 3 |
| 76 | 342 | 1.285295 | 24.405658 | 15.868944 | 40.274602 | 9 → 4 |
| 54 | 303 | 1.167235 | 20.563290 | 17.287737 | 37.851027 | 13 → 5 |

For each reviewed page, base-term sums reproduce its saved stopword score, and
all-term sums reproduce its saved expanded score within 1e-12. The small differences
between rounded totals are rounding, not unexplained score residuals.

Page 61 has two occurrences of profit and none of the other seven additions. Its
gain is exactly that term's 4.635431573785596 contribution. Page 63 gains especially
from purchases: DF=6, TF=2, contribution=5.860928417929998. Page 46 gains from seven
added terms, including repeated capital and spending. The income statement's short
length already gives it favorable length normalization; document length alone does
not explain why it misses the cutoff. Missing query/operand vocabulary and competitor
matches are the immediate lexical mechanism.

The original question's term define has DF=2 and contributes 7.165591 on page 46,
which contains non-GAAP definitions. The phrase assuming also matches that page,
contributing 2.949535. These are existing question-word effects, not expansion
effects. Other original terms analyst, answer, capex, EBITDA, FY, perspective,
unadjusted and USD have DF=0 here and contribute nothing. No instruction cleanup,
stemming, synonyms, or query-weight change is made as part of this diagnostic.
Question cleanup would be a separate ablation rather than part of section context.

The expanded top five remain [63,46,53,76,54]. Offline annotated pages are {61,63};
only 63 is present. The previously verified Recall@5=0.5 and reciprocal rank=1
therefore remain compatible with missing a necessary income-statement operand.
No automated answer is produced. Reviewer arithmetic of 9,068 USD million remains
an offline reference calculation from the earlier review.

## Source inspection of all five multi-page questions

All nine unique annotated report/page pairs are now inspected in native text;
the two PepsiCo numerical questions share pages 61/63. Labels select this offline
review sample and never enter retrieval/context construction.

| Question | Native pages | Confirmed source structure | Implication |
|---|---|---|---|
| 03069 AMD D&A margin | 55,59 | Page 55 starts Item 8 plus Statements of Operations; 59 starts Cash Flows. Revenue 3,991 and D&A 167 are present in the 2015 columns, in millions. Intermediate pages have other statement titles. | These are separate tables, not one missing continuation page. Reset local table context between titles. |
| 01290 Boeing customers | 7,9,13 | Page 7 changes from forward-looking prose to Item 1A and business/operations risks, then airlines; 9 changes mid-page to defense spending; 13 changes to contract risks and the 2022 40% government-contract statement. | One item label cannot express multiple local risk topics. FY24 appears in forward-looking defense prose; it is not a year override for all evidence. |
| 01009 PepsiCo geographies | 3,4 | Page 3 changes from forward-looking statements to Business, Overview, Operations and list entries 1–5. Page 4 starts entries 6–7, then division descriptions. | Inherited Operations context fits the opening continuation, not the whole page. A page can contain multiple spans/headings. |
| 03620 PepsiCo EBITDA less capex | 61,63 | Income statement contains Operating Profit 11,512; Cash Flows contains D&A 2,763 and capital spending (5,207). Both have fiscal-year columns and millions units. | Missing evidence is already extracted. Context must not confuse accounting-policy definitions with observed fiscal operands. |
| 04481 PepsiCo EBITDA margin | 61,63 | Same tables, with Net Revenue 86,392 also on 61. | Shares the missing income-statement dependency; retrieving Cash Flows alone does not establish the ratio. |

Native/annotation snippets are not byte-identical in every case. AMD and PepsiCo
financial pages include dash placeholders omitted from the supplied annotation
snippets. PepsiCo page 3 additionally preserves navigation text and quotation marks.
Boeing's three short snippets and PepsiCo page 4's list-continuation snippet are
contained after the frozen whitespace/NFKC normalization. The reviewed operand
values, year columns, and topic/list structures agree; this is not a comprehensive
PDF transcription-quality test. Parentheses and dash placeholders must remain in
raw source text for any later financial extraction/sign interpretation.

## Trace competitors now identified

| Page | Native content | Why its lexical score is not sufficient answer support |
|---|---|---|
| 46 | Non-GAAP definitions of constant-currency performance, free cash flow and ROIC | Contains formula/definition vocabulary, not the needed income-statement row. |
| 53 | Free-cash-flow reconciliation and commentary | Includes the real capex magnitude (5,207), so it is partly relevant, but lacks the required Operating Profit. |
| 76 | Intangible-asset impairment discussion, then Other Significant Accounting Policies including a Property, Plant and Equipment bullet | General accounting prose matches operating profit/cash flows/capital/PP&E; it does not supply the requested fiscal operand rows. |
| 54 | Material changes in consolidated balance-sheet line items, with depreciation/capital-spending footnotes | Its explicit unit is **billions**, unlike the statement's millions; section-wide unit inheritance would be unsafe. |

Repeated Table of Contents text is a navigation prefix on these pages, not their
semantic heading. It appears at raw offset 0 on the selected PepsiCo pages; their
actual headings/content start afterward. PepsiCo page 2 is an actual contents page;
page 30 is an Item 7 subcontents listing with page references. Detecting a repeated
prefix alone neither locates contents pages nor establishes the current section.

## Observed source pointers and boundaries

Offsets below are **zero-based Python Unicode character offsets into raw_text**,
with end exclusive. They are not byte offsets, normalized-search-text offsets,
printed page numbers, bounding boxes, or PDF geometry. Each is an exact observed
span; interpreting its scope is an offline reviewer judgment.

| Report | PDF page | Raw span [start,end) | Observed text |
|---|---:|---|---|
| AMD 2015 | 55 | [4,55) | ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA |
| AMD 2015 | 55 | [85,122) | Consolidated Statements of Operations |
| AMD 2015 | 59 | [33,70) | Consolidated Statements of Cash Flows |
| Boeing 2022 | 7 | [845,866) | Item 1A. Risk Factors |
| Boeing 2022 | 7 | [1192,1236) | Risks Related to Our Business and Operations |
| Boeing 2022 | 9 | [2264,2317) | Changes in levels of U.S. government defense spending |
| Boeing 2022 | 13 | [764,794) | Risks Related to Our Contracts |
| PepsiCo 2022 | 3 | [18,44) | Forward-Looking Statements |
| PepsiCo 2022 | 3 | [2028,2045) | Item 1. Business. |
| PepsiCo 2022 | 3 | [2872,2886) | Our Operations |
| PepsiCo 2022 | 4 | [18,27) | 6) Africa |
| PepsiCo 2022 | 4 | [178,193) | 7) Asia Pacific |
| PepsiCo 2022 | 4 | [374,397) | Frito-Lay North America |
| PepsiCo 2022 | 61 | [18,50) | Consolidated Statement of Income |
| PepsiCo 2022 | 63 | [18,54) | Consolidated Statement of Cash Flows |
| PepsiCo 2022 | 63 | [2076,2105) | (Continued on following page) |
| PepsiCo 2022 | 64 | [18,66) | Consolidated Statement of Cash Flows (continued) |
| PepsiCo 2022 | 76 | [1942,1979) | Other Significant Accounting Policies |
| PepsiCo 2022 | 130 | [0,12) | Exhibit 4.65 |

PepsiCo 2022's explicit Item 8 heading is on page 117 and cross-references Item 15;
the actual statement titles are on pages 61 onward, earlier in the report's Item 7
sequence. Inferring every financial table from an Item 8 interval would miss them.
AMD's Item 8 and statements are colocated; that pattern does not transfer unchanged.

The cash-flow table explicitly continues from 63 to 64. That is different from the
separate income statement on 61: blindly adding one neighbor to cash-flow page 63
would not reach it. Adjacency and heading enrichment should remain separate effects.

The long PepsiCo documents include appended securities descriptions, benefit-plan
documents, subsidiary lists, powers of attorney and certifications. Source inspection
around the primary-report ending shows:

| Report | Signatures | First attached exhibit | Remaining physical pages from exhibit start |
|---|---|---|---:|
| PepsiCo 2019 (667 pages) | 145–146 | 147: Exhibit 4.62 | 520 |
| PepsiCo 2022 (503 pages) | 128–129 | 130: Exhibit 4.65 | 373 |

These are observed boundary examples, not a complete automatic segmentation audit.
Attachment page numbering/headings restart; later plan documents contain their own
contents and ARTICLE headings. Carrying the annual-report heading/year/unit through
the entire file would contaminate context. Reset at source-derived attachment
boundaries and handle subsequent exhibits independently. **Do not remove attachments
from the candidate set or recompute a main-report-only BM25 control.** The frozen
control includes every physical page; candidate pruning would be another condition.

## Next structural design, before a new experiment

The source review is now sufficient to start a deterministic heading/span prototype.
It does not establish that heading context will recover all five gold sets. Start
with these constraints when specifying the new condition:

1. Keep expansion v1 and the all-page source store frozen. Source context construction
   reads document/page text only, sequentially and independently of the questions or
   review-selected pages. No manual page-role table from this document enters code.
2. Detect exact raw-line heading spans with source page/offset and a declared rule ID.
   Separate observed titles from inferred inherited labels. Support multiple local
   headings on one page; recognize statement titles as well as item/risk headings.
   Distinguish actual headings from contents listings and prose cross-references.
3. Propagate only declared heading context to an opening continuation, stop at a new
   observed local heading, and reset at report/exhibit boundaries. Treat detection
   confidence and scope as weak labels. Do not propagate year/currency/unit metadata
   in the first heading-only condition; table-local evidence remains authoritative.
4. Freeze an explicit per-page heading-token cap, duplicate-heading treatment,
   ambiguous-heading behavior, ranking rule and index-normalization behavior before
   its run. Account for the extra text/storage/build cost. Identical source headings
   already on a page are not new evidence; repeating them is a weighting choice.
5. Compare that single structural change against the unchanged expansion control
   at k=1/3/5 with complete-evidence coverage and paired question ranks. Keep adjacency,
   question cleanup, operand-aware reranking and ledger retention out of this first
   ablation. A later extractor must also enforce the proposed five-page/4,096-model-
   token budget; today's lexical page tokens are not an extractor-model token count.

Before a corpus run, validate source-only heading detection on diverse report pages,
including non-evidence pages and the boundary examples above. Do not tune only to
these five labeled questions or infer held-out performance from this development
diagnostic. Final heading rules/caps and their results remain pending implementation
and real execution outputs.

## Validation and Windows commands

The patch against b15a868 adds this diagnostic, README/current-state links, the
offline helper and six tests. No src/ implementation or frozen snapshot changes.
All **83 tests pass** locally, including independent hand-formula attribution,
blank-page/binary-frequency handling, zero-score tie/scope rejection, full-candidate
reproduction without source PDFs/tasks, cache tampering, query-label rejection even
after rehashing, and duplicate physical-page detection. Fixture results validate
software only. PowerShell is not available in this environment; the helper's Python
entry point is executed here against the actual uploaded artifacts.

Apply from the clean pushed checkpoint, preserving any local edits:

```powershell
Set-Location "$env:USERPROFILE\Downloads\Research-Seminar-OCR-current"
git status --short
git log -1 --oneline
$patchFile = "$env:USERPROFILE\Downloads\native-cache-review.patch"
git apply --check $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; preserve local changes." }
git apply $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
```

Optional local diagnostic reproduction; this rereads existing outputs and does not
run PDF extraction or a new retrieval condition. Set expansionDir to the **existing
expansion directory** containing run_manifest.json and expanded_predictions.jsonl;
its parent folder name is not necessarily the internal run_id. Use a fresh output:

```powershell
$dataRoot = "$env:USERPROFILE\financial-ocr-data"
$nativeDir = Join-Path $dataRoot "derived\native\native-bm25-20261008T051510Z-7fcc394d"
$expansionDir = Read-Host "Full path to the existing financial query-expansion run directory"
if (-not (Test-Path -LiteralPath (Join-Path $expansionDir "expanded_predictions.jsonl"))) {
    throw "Select the completed expansion run, not the native or stopword run."
}
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$diagnostic = Join-Path $dataRoot "derived\diagnostics\native-cache-$stamp.json"
& .\.venv\Scripts\python.exe .\scripts\diagnose_native_cache.py `
  --native-dir $nativeDir `
  --expansion-dir $expansionDir `
  --task-id "financebench:financebench_id_03620" `
  --pages 61 63 46 53 76 54 `
  --output $diagnostic
if ($LASTEXITCODE -ne 0) { throw "Diagnostic reproduction failed." }
```

The delivered `native-cache-score-diagnostic.json` already records the successful
reproduction from the supplied files. Its input paths refer to this local analysis
workspace; checksums/run IDs, rather than temporary directory names, identify the
source artifacts. Running the helper on Windows writes the user's local paths.
Keep the cache and diagnostic JSON outside Git. This document contains label-exposed
review information; exclude it, the earlier review and score diagnostic from
retrieval inputs, extractor prompts and ledger/correction memory.
