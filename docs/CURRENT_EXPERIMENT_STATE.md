# Current experiment state — 2026-10-08

Read this before continuing the experiment. This records the current verified Windows setup and supersedes historical experiment descriptions where they conflict. Do not report proposed work as completed results.

## Research goal

Study whether a compact financial-document pipeline can preserve relevant evidence using OCR, retrieval, section context, and bounded source-linked memory while controlling processing cost. FinanceBench is the primary dataset. Comparing one-shot and pagewise OCR remains a possible component, not the entire research question. Fine-tuning and transfer to other business documents are later possibilities, not completed work. MMLongBench-Doc and InduOCRBench are outside the primary experiment.

## Windows setup

- Repository: https://github.com/mbarroso22/Research-Seminar---OCR-.git
- Clone: C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current
- GitHub base commit: bfa5a46. Local audit and sector patches have been applied; their presence on GitHub is not confirmed.
- Python: 3.13.7; repository-local .venv. Activation is unnecessary when invoking .venv\Scripts\python.exe directly.
- Editable install succeeded. pypdf, cryptography, and fonttools installed.
- All 27 tests passed on the user's machine after the sector fix.
- DATA_ROOT: C:\Users\mbarroso\financial-ocr-data
- Metadata: DATA_ROOT\raw\financebench\data\financebench_document_information.jsonl
- Questions: DATA_ROOT\raw\financebench\data\financebench_open_source.jsonl
- PDFs: DATA_ROOT\raw\financebench\pdfs
- Current audit: DATA_ROOT\audits\financebench_phase0_sector_fixed
- Hardware previously reported: i5-12600K, 16 GB RAM, RTX 3060. Confirm current machine and GPU VRAM before model installation.

## Verified dataset findings

368 physical PDFs; 361 metadata rows representing 360 unique document names. Types: 269 10k, 6 10k_annualreport, 27 10q, 30 8k, 29 Earnings. The annual-report entries represent 274 unique reports across 40 companies.

150 questions cover 84 documents. Of those, 112 questions cover 64 annual reports. Each question includes a reference answer and evidence; supporting text and justification are evaluation material, not retrieval inputs. Evidence page numbers are zero-based PDF indices, not printed page labels.

The full audit remains blocked: FOOTLOCKER_2023_annualreport occurs twice with identical URL but reporting years 2023 and 2022; two Intel 2023 8-K PDFs fail parsing; eight PDFs lack metadata. Preserve originals. No year has been corrected and the Intel files have not been repaired. Audit readability counts are metadata-row counts, not counts of distinct physical PDFs.

Three Adobe failures were resolved by installing cryptography. The two associated evidence-page errors disappeared; they were consequences of unreadable PDFs, not demonstrated incorrect annotations. gics_sector mapping was fixed in code and tested.

## Fixed development pilot

| Company | Sector | Years |
|---|---|---|
| AMD | Information Technology | 2015, 2019, 2022 |
| Best Buy | Consumer Discretionary | 2015, 2019, 2023 |
| Boeing | Industrials | 2015, 2019, 2022 |
| PepsiCo | Consumer Staples | 2015, 2019, 2022 |

12 reports, 2,620 pages, 24 questions across six reports, and 25 distinct annotated evidence pages. Five questions have multiple evidence pages. Question types: 15 domain-relevant, 4 metrics-generated, 5 novel-generated.

Separate validate-data run on pilot_documents.jsonl and pilot_tasks.jsonl returned valid=true, 12 documents, 24 tasks, no errors or warnings, 12 OCR-ready documents. Pilot mappings were checked against original annotations and matched. Native text was sampled, not extracted from every page yet. PepsiCo reports with 667 and 503 pages require structural inspection.

Pilot manifests: current audit\manifests\pilot_documents.jsonl and pilot_tasks.jsonl. This is a DEVELOPMENT pilot, not a held-out evaluation cohort. Six unannotated reports support processing comparisons, not annotated QA scoring.

## Next phase: implement the native-text retrieval baseline

1. Extract all pages from the fixed pilot PDFs, preserving doc_id and zero-based page index. Record blank pages and extraction failures, checksums, tool version, configuration, and elapsed time. Process reports sequentially and save derived outputs outside Git.
2. Build a simple reproducible lexical page-retrieval baseline, initially BM25 within each question's specified report. Index all report pages. Retrieve with question text only; exclude answers, justifications, evidence text, and known evidence indices from retrieval and memory.
3. Save ranked pages and scores per question. Evaluate against annotations afterward: evidence recall, any-evidence hit, and all-evidence coverage at fixed k (initially 1, 3, 5). Distinguish these metrics and report question counts. No answer generation is included in this first baseline.
4. Inspect extraction and long-report structure. Native text is a comparison reference, not verified OCR transcription ground truth.
5. Later run an OCR diagnostic on the 25 evidence pages; this is oracle-selected diagnostic work, not end-to-end retrieval evaluation. Full-report OCR is needed for fair OCR retrieval comparison.
6. Then compare ordinary retrieval, section context, and bounded source-linked memory under matched budgets. Define separate company/document held-out boundaries before claims of generalization or training.

## Not completed

No full-page native-text baseline or retrieval results. No OCR model execution, answer-generation evaluation, contextual-memory implementation, fine-tuning, latency benchmark, measured energy savings, or generalization result. Do not invent these results or reuse synthetic test outcomes as experimental measurements. OCR adapter placeholders and proposed protocol text are not functioning model integrations.

## Handoff instruction

Read this file, PROJECT_HANDOFF.md, docs/MEMORY_EXPERIMENT_PROTOCOL.md, relevant source, and tests. Resolve conflicts in favor of verified current-state evidence. Inspect git status before editing; preserve applied patches and originals. Implement the native-text baseline and meaningful tests, provide a patch and Windows commands, and wait for the user's real run output before reporting experimental results. The assistant cannot access the user's Windows filesystem or PDFs directly.

## Detailed technical roadmap

Read `docs/TECHNICAL_RESEARCH_ROADMAP.md` for the paper relationship, provisional model choices, architecture, execution stages, data boundaries, budgets, scoring, cost accounting, implementation backlog, and handoff instructions. Its 35 sections distinguish verified state from proposals. Model names in the roadmap are not evidence of installation or successful inference.

## Phase 1 implementation handoff (2026-10-08)

The repository continuation is based on confirmed Git commit
`5cf284233702edf82ed8f2bb496600eae76107a4`; the earlier `bfa5a46` setup reference
above is historical. The native-text/BM25 CLI baseline is now implemented and tested
locally on small fixtures. It has **not been run on the user's FinanceBench PDFs**.
The pilot remains development-only; no empirical recall, latency, OCR, or answer
correctness result has been established by this implementation.

Read `docs/NATIVE_BASELINE_WINDOWS.md` for patch application, the existing .venv,
`scripts/run_native_pilot.ps1`, direct Windows commands, output contracts, and the
files to return. Runtime retrieval accepts only `task_id`, `doc_id`, and `question`.
Scoring reads labels after predictions are saved. Every expected page and question
is accounted for, including failed/empty native text, with zero-based IDs preserved.
Source hashes/page counts and configuration/provenance are recorded. Resume is
explicitly unsupported; use a new output directory for each run.

The next experimental action is execution on the validated 12-report pilot and
inspection of its real output artifacts. Keep the corpus results pending until those
outputs are supplied. Earlier roadmap rows naming the native baseline as a proposed
module now refer to implemented code; other OCR/context/memory stages remain proposed.

## Verified native baseline and diagnostic continuation

The researcher supplied a completed Windows run and its artifacts on 2026-10-08:
`20261008T051510Z-7b1970c7f4e8`. All 12 reports/2,620 pages were attempted, with
zero extraction failures and seven pages with empty native text. PDF checksums and
observed page counts matched the frozen pilot. All 24 rankings were present.
Independently recomputed Recall@5 was 28.47%, any-evidence Hit@5 was 8/24, and
all-evidence coverage@5 was 6/24. No answer generation or OCR comparison has run.
This supersedes the earlier statement that native corpus execution was pending.

The supplied 25-page native-text diagnostic shows financial line items on missed
evidence pages, competing exhibit/boilerplate pages, terminology mismatches, and some
damaged native text. This is label-selected offline inspection, not new evaluation.
Read `docs/NATIVE_DIAGNOSTIC_FINDINGS.md` for exact observations and next commands.

A separate cached-page stopword-only comparison is implemented with 61 passing local
fixture tests. It reproduces original rankings before accepting new results, keeps
the complete page scope and labels out of retrieval, and writes to a new directory.
Its Windows/corpus execution and accuracy changes remain pending real user outputs.
Do not report it as an improvement yet or use the diagnostic page subset as its corpus.

## Verified stopword-only development comparison (2026-10-08 EDT)

The researcher supplied completed comparison run `20261009T012131Z-1e32aa99fc79`
(2026-10-08 21:21 EDT). Uploaded artifact hashes/sizes, the original baseline
manifest identity, frozen task checksum, minimal query projection, zero-based
full-report candidate rankings, original ranking reproduction, and independently
recomputed metrics all passed review. The delivered Python source digest matched
the recorded Windows CRLF source bytes. This supersedes the pending-execution
statement above. The complete native-page cache was not uploaded for this review;
its checksum and full-cohort validation are recorded by the completed runner.

Across the same 24 development questions, stopword-only Recall@1/@3/@5 was
8.33%/26.39%/30.56%, compared with 6.25%/20.14%/28.47% for the frozen baseline.
Any-evidence Hit@5 increased from 8/24 to 9/24; all-evidence coverage@5 stayed
6/24. Full-ranking MRR increased from 0.208245 to 0.246135. At k=5, only AMD
2015 D&A question 03069 gained recall: cash-flow page 59 moved from rank 6 to 1,
but operations page 55 remained outside top five (rank 64 to 25). All five
multi-page questions still lacked complete evidence coverage@5. Some evidence
pages regressed deeper in the ranking; the result is a limited development gain.

Keep the original baseline and stopword variant as separate conditions. This is
retrieval evidence scoring, not answer correctness, OCR accuracy, measured energy,
or held-out generalization. No new OCR or answer-generation result is established.
See `docs/STOPWORD_COMPARISON_RESULTS.md` for the verified metrics, paired changes,
provenance, limitations, and the next diagnostic recommendation.

## Next implemented experiment: question-only financial-term expansion

Continuation starts at pushed commit `3550ba2f352a9be216455275559fbf0c9bbc3a1e`.
The next development ablation tests a fixed 12-rule financial-term expansion of
question text on the unchanged stopword page index. This addresses the diagnostic
terminology gap without mixing in OCR, page enrichment, section cues, adjacent-page
packing, or memory. It is explicitly development-designed after labeled review.

`compare-query-expansion` reuses the full native cache and requires the matching
saved stopword comparison. It reproduces both controls, records the exact versioned
rule policy and expanded questions, and saves all three rankings before loading
annotations for scoring. Source IDs remain zero-based and the complete within-report
page scope is preserved. Primary comparison is expansion versus stopwords; original
BM25 is a second frozen control. Outputs go to a new directory outside Git.

Read `docs/QUERY_EXPANSION_EXPERIMENT.md` for the frozen policy, commands, output
contract, and required returned artifacts. All 76 local fixture tests pass. No
full-pilot expansion outcome is available yet; report new experimental results only
after the researcher supplies the real execution outputs. The earlier verified
original and stopword results remain separate conditions, with no answer or OCR
accuracy claim.

## Verified question-expansion development results (2026-10-08 EDT)

The researcher supplied complete Windows run `20261009T020622Z-76a16239e13d`
(22:06 EDT). All seven uploaded artifact hashes/sizes match. Both earlier control
rankings and scores reproduce; all 24 expanded query/audit records reproduce from
the minimal original question projection. The package-source digest matches the
delivered Windows CRLF implementation. Independently recomputed metrics agree.
This supersedes the preceding pending-expansion-outcome statement.

Expansion changed six questions; the other 18 retain exact stopword rankings.
Recall@1/@3/@5 is 10.42%/32.64%/40.97%. Against the fixed stopword control,
Recall@5 rises by 10.42 percentage points, any-evidence Hit@5 goes from 9/24 to
12/24, all-evidence coverage@5 from 6/24 to 8/24, and full-ranking MRR from
0.246135 to 0.302408. Three questions gain Recall@5 and none lose it: AMD 2022
quick-ratio page 55 reaches rank 5, AMD operating-margin page 42 reaches rank 3,
and PepsiCo EBITDA-margin cash-flow page 63 reaches rank 1. Its operations page
61 remains at rank 24. All five multi-page questions still lack complete top-five
coverage. Some deeper operand ranks regress (PepsiCo EBITDA-less-capex page 61:
17 to 23), despite no measured-cutoff recall losses.

Read `docs/QUERY_EXPANSION_RESULTS.md` for the full verified review and limitations.
Freeze all three conditions and v1 query rules. A separate source-derived section
context ablation is the next proposal; no structural, OCR, answer-generation,
ledger-memory, or held-out generalization result has run. This remains a labeled
development pilot. The complete native-page cache was not uploaded for local score
reconstruction; its coverage/checksum validation is recorded by the completed runner.

## Advisor-directed review before section context (2026-10-09)

Continuation starts at pushed commit `585390fe08fc2d719b72c78c4384881cd135ad8b`.
Expansion v1 is frozen as the development control: policy SHA-256
`80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3`.
`docs/EXPANSION_V1_CONTROL.json` records its exact policy/configuration and reference
input/output identities. A fingerprint test guards against silent rule changes;
the retrieval implementation is unchanged. The original and stopword conditions
are retained. Future changes are separate conditions, not edits to this control.

The supplied pilot_tasks.jsonl matches the frozen 24-task checksum. All five
multi-page questions were reviewed using actual saved rankings, annotation evidence,
and the supplied native diagnostic where available. Their structures differ:
separate financial statements (AMD and two PepsiCo metrics), dispersed customer
prose (Boeing), and an adjacent-page operating-geography list (PepsiCo). There are
11 task/page references but nine unique report/page pairs; the two PepsiCo numerical
tasks share the same statement pages. Native inspection covers four of those unique
pages; the other five currently have annotation full-page text only.

The detailed trace is PepsiCo question 03620. It preserves the minimal query,
adds eight fixed terms, indexes all 503 report pages, and retrieves [63,46,53,76,54].
Page 63 contains D&A/capex. Missing page 61 contains Operating Profit; its score
increases from 18.811897 to 23.447328 while rank worsens from 17 to 23. Other pages
gain more score. Source TF counts support broader capex matching, but exact DF/
average-length/term contributions require the complete native cache. Offline scores
are Recall@5=0.5, hit=1, complete=0, reciprocal rank=1. Reviewer arithmetic is not
an automated answer result; the pipeline stops before answer extraction/generation.

Read `docs/MULTIPAGE_REVIEW_AND_PIPELINE_TRACE.md`. Per advisor feedback, section
context remains unimplemented. Obtain the original native_pages.jsonl for exact
score attribution and source heading/boundary checks before choosing a section
policy. Exclude the label-derived review document from retrieval/context/memory.
The source store must remain complete; repeated navigation headers, multiple
headings per page, list continuation, risk prose, and statement boundaries need
separate treatment. No new corpus experiment or held-out result has run.

## Complete native-cache diagnostic (2026-10-09)

Continuation starts at pushed commit `b15a868`. Its README preserves the verified
stopword/expansion results; omitted frozen-control and review links are reconciled
without replacing those results. Expansion v1's policy and control snapshot remain
unchanged. No files under src/ are changed by this continuation.

The uploaded native_pages.jsonl matches the original manifest exactly: SHA-256
`c6de36446465cc9bdc27dfbf1dde2bc24c5cdd7f6b52a57b0f03fd7358d03a52`,
16,163,945 bytes, 12 reports, 2,620 zero-based contiguous page records, 2,613 with
native text and seven with no native text, zero failures. All extraction provenance,
normalization, source identities, counts and statuses match the extraction summary.
The cache is no longer missing; earlier upload/inspection limitations are historical.

All 24 questions' original, stopword and expansion full rankings reproduce from the
cache: 72 rankings, 15,717 page scores, maximum absolute score difference
7.105427357601002e-15. This is reproduction of the user's existing execution, not
a new treatment, accuracy improvement or timing benchmark. No labels are loaded
by the new offline helper. Selected diagnostic pages never filter its full indexes.

The 03620 trace now has exact term attribution: N=503, total stopword page tokens
124,621, average length 247.7554671968191. Page 61 gains only the added word profit
(4.635432); competitors match more capex terms. Page 76 is accounting-policy prose,
and page 54 is balance-sheet change commentary in billions, not the missing income
statement in millions. All nine unique annotated multi-page source pages have now
been inspected in native text, including Boeing's risk prose and PepsiCo's split list.

PepsiCo statement titles precede the explicit Item 8 cross-reference. Its list on
page 4 changes to local division headings at raw offset 374. Cash-flow page 63
explicitly continues to 64. Signatures/exhibits establish attachment reset boundaries
at 2019 pages 145/147 and 2022 pages 128/130. Keep all attachments as candidates.
Observed native offsets are text pointers, not verified PDF geometry/transcription.

Read `docs/NATIVE_CACHE_DIAGNOSTIC.md` before choosing the section policy. The
offline `scripts/diagnose_native_cache.py` validates artifacts, reproduces saved
rankings, and writes score attribution outside Git. Six diagnostic regression tests
bring the suite to 83 passing tests. Section context remains unimplemented; source
heading extraction, context resets and declared heading-token budgets are the next
design/implementation work. Keep all review documents and diagnostic outputs out
of retrieval inputs, prompts, and ledger memory.

## Source-derived section comparison implementation (2026-10-12)

Continuation starts at pushed commit `dae9897`. `finocr compare-section-context`
now compares a fixed source-derived heading field against frozen expansion v1.
Implementation and fixture verification are complete; new experimental results
remain pending the researcher's real Windows execution. None are reported here.
The earlier native-cache diagnostic/review and all verified results remain intact.

Policy: source-local-headings-v1, SHA-256
`159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e`.
The exact policy is checked in at configs/section_context_v1.json and copied into
each new run manifest. The unchanged expansion-v1 body BM25 score is augmented
by 0.25 times a separate heading BM25 score. The heading field contains at most
64 frozen-stopword tokens per page, including complete observed local headings
and eligible opening continuation. Body DF/lengths/average length remain unchanged.
The heading index has its own DF/length statistics over the very same physical pages.

Context reads only doc_id, zero-based page_index and raw_text, traversing full reports
in source order without questions or labels. It records observed raw spans and weak
inherited scopes; the last locally observed heading may carry to the next physical
page's opening only, ends at its first new heading/reset, and never chains across
more pages. Contents listings, navigation/footer-only or blank pages, signatures,
exhibit-index lines, standalone top-of-page exhibits and filing covers clear state.
No currency/year/unit inheritance, adjacency, query cleanup or ledger is combined.

The runner verifies immutable inputs and lineage, reproduces original/stopword/
expansion full rankings and queries, saves all context/query/prediction artifacts,
then parses frozen labels for offline scoring. It also checks that all three control
metrics reproduce. Full-report candidates, blank pages, attachments, zero-based
IDs and ties remain fixed. The original pipelines and expansion-control snapshot
are unchanged. Both inputs are the saved original native and expansion-v1 runs;
the old stopword run directory need not be loaded again.

All 103 tests pass (83 prior plus 20 new). Source-only smoke checks confirm the
reviewed local statement/risk/list heading offsets, PepsiCo page 4's opening scope
ending at raw offset 374, and the 2019/2022 exhibit resets. No new corpus ranking or
metric was executed for these smoke checks. Source-derived headings remain weak
heuristics without PDF line geometry; they are not verified semantic segmentation.

Read docs/SECTION_CONTEXT_EXPERIMENT.md and scripts/run_section_context.ps1 for
exact PowerShell commands, immutable outputs, acceptance checks and artifacts to
return. Reuse cached extraction, create a new run outside Git, and wait for actual
outputs before reporting structural retrieval effects. No OCR, answer-generation,
ledger-memory, timing/energy benchmark or held-out generalization result is added.

## Verified section-v1 development results (2026-10-12)

The user supplied section-context-results.zip after successful Windows execution.
Internal run ID: `20261013T010312Z-967cd9567b9c`; folder suffix: `1a0d48a0`.
Execution was October 12 at 21:03 EDT (October 13 at 01:03 UTC). All 11 files are
present, ZIP CRC checks pass, and all ten artifact byte hashes/sizes match the manifest.
The executed Python source digest matches the delivered implementation with CRLF
newlines. Base commit dae9897 plus the applied implementation patch is recorded dirty;
no new pushed implementation commit is assumed by this review.

The frozen expansion reference is unchanged. All input identities, policies, minimal
queries and audits match. The full original native cache remains available locally.
All 2,620 context records reproduce, including raw spans, source hashes, inherited
one-page pointers, caps/resets and the structural summary. All 96 full rankings
reproduce, with 20,956 page scores checked and maximum absolute difference
7.105427357601002e-15. All per-question/aggregate/subgroup metrics, MRR and deltas
were independently recomputed without the pipeline evaluator and match the upload.

Compared with frozen expansion v1, Recall@1/3/5 is unchanged (10.42%, 32.64%, 40.97%).
Hit@5 remains 12/24 and complete coverage remains 8/24. Every question's Recall@5 is
unchanged. At k=3, AMD quick-ratio gains one complete page (rank 5 to 3), canceled by
Best Buy acquisitions losing its gold page (rank 3 to 4). Full MRR improves from
0.3024075204503773 to 0.31477955742883584: nine first-evidence ranks improve, three
regress and twelve stay fixed. This is a secondary ranking gain, not a coverage gain.

All five multi-page cases remain incomplete at k=5: AMD D&A stays 1/2, Boeing
customers 1/3, PepsiCo geographies 0/2, EBITDA-less-capex 1/2, EBITDA margin 1/2.
Missing income-statement page 61 improves from 23 to 19 and from 24 to 20 in the
two PepsiCo questions, but remains outside the cutoff. Geographic page 4 improves
20 to 13; page 3 stays 228. Boeing pages 7/13 worsen 39 to 46 and 161 to 162,
despite their headings being detected: their heading fields have zero query overlap.

Context adds 14,633 capped lexical tokens on 1,662 pages and stores 1,908,325 bytes
of page context. Observed column labels can be mistaken for section headings,
including Year Ended and a division-name table header. Bare numbered Best Buy notes
and en-dash Note headings are missed by the fixed v1 grammar. These are demonstrated
limitations, not a measured overall heading precision/recall estimate.

The single Windows run records 1.924067 seconds total wall time and 0.701294 seconds
context construction. Section-query total for 24 questions is 0.029820 seconds
versus 0.016828 for expansion. These include declared processing/validation costs;
they do not establish repeated query latency or energy savings.

Read docs/SECTION_CONTEXT_RESULTS.md. Preserve expansion v1 as the development
control and keep section v1/run outputs as a fixed completed ablation. No source
policy, weight, candidate set, query or implementation changes are included in this
results update. Review heading precision and missed formats before a separate v2
or ledger experiment; do not assume more heading weight will recover all operands.
This remains label-exposed development retrieval evidence, not answer correctness,
OCR quality or held-out generalization. Exclude results/review artifacts from inputs.

## Detection-versus-matching review and next experiment (2026-10-12)

Continuation starts at pushed `10e91145bd6b9530c2f43f18c9e91512f2173093`, which
contains section v1 and its verified results. Expansion v1 remains the development
control. Runtime, policies, configs, tests and saved run artifacts are unchanged.
This is an offline source/failure review, not a new condition or new metric execution.

Read docs/HEADING_FAILURE_REVIEW.md. The review separates heading detection and
scope correctness, lexical query overlap, and cutoff/ranking sufficiency. Selected
native-text examples and saved score components support the diagnoses; they do not
provide population heading precision/recall or PDF geometry verification.

An additional directly relevant detection failure is Boeing 2022 page 111's
`Note 21 – Legal Proceedings`, raw span [2122,2149). Its en dash is unsupported by
v1, and legal is a query token for question 01091. V1 instead carries Fair Value
Disclosures across page 112, where legal prose continues before `Note 22 – Segment
and Revenue Information` at [2429,2470). That second missed heading has zero overlap
with the legal query: a missing boundary can matter even when its own title does
not supply search terms. Best Buy page 50's missed `2. Acquisitions` does match
question 01077; its missed `3. Restructuring` does not.

Other failures are different. Boeing customer headings are detected correctly and
match none of that question's tokens. PepsiCo's Operations heading/continuation is
correct, but operations and operates differ; page 4's only heading overlap is the
company term pepsico. AMD's correct Statements of Operations title does not match
P&L statement wording. PepsiCo's correct Income title matches income/statement and
gets a positive score, yet page 61 stays outside the top five in both calculations.
These cases cannot all be attributed to detection errors or fixed by larger weights.

Spurious title/state examples include Year Ended, a PepsiCo division table header,
and Best Buy page 46's wrapped prose line `Consolidated Statements of Earnings from
the fair value of the derivatives.` The latter is incorrectly accepted as a statement
heading. These quality issues remain recorded independently of query usefulness.

Recommended next controlled experiment: a separately versioned **note-format coverage
ablation**. Add en-dash Note headings and cautiously gated bare-number note headings
inside a source-observed notes region. Keep generic-title/prose rules, query expansion,
tokenization, weight 0.25, 64-token cap, one-page continuation, resets, candidates and
body scores fixed. New heading boundaries naturally change context scopes and heading
index statistics; record those consequences rather than treating the heading index
as unchanged. Source hard-negative checks must reject contents references, numeric
tables and numbered non-note lists; no company/page/answer lookup table is permitted.

Compare the proposed condition with saved section v1 to isolate note recognition;
also compare with expansion v1 for the overall structural effect. No new rule or
code is implemented yet. Do not bundle table-label cleanup, query stemming/synonyms,
weight search, adjacency, statement-family selection or ledger retention into this
first ablation. Better detection is a testable hypothesis for lost legal/acquisition
heading signal, not a promised recovery of the five multi-page evidence sets.

## Final planned heading-format ablation implemented (2026-10-13 UTC)

Continuation starts at pushed `7ebb8f5`. `finocr compare-note-formats` and
`scripts/run_note_formats.ps1` implement the authorized note-format coverage
comparison. Expansion v1 remains the development control; section v1 remains
the saved structural comparator. No new experimental retrieval results are
reported until the user executes locally and supplies the new run artifacts.

The new source-only policy supports U+2013 en-dash Note titles and bare `N. Title`
lines only after an exact standalone Notes to Consolidated Financial Statements
parent. A bare chain must start at 1 on the parent page and then follow consecutive
numbers; prose mentions, sequence gaps/repeats, unsupported title syntax, numeric
tables and page references are rejected with source pointers/reasons. Region
eligibility clears at observed Item boundaries and all existing resets. Its state
permits recognition, not multi-page heading-text or financial-variable retention.
Read docs/NOTE_FORMAT_EXPERIMENT.md and configs/note_formats_v1.json.

Scoring/tokenization/expansion, heading weight 0.25, cap 64, continuation/reset
rules, raw zero-based page IDs, full-report candidates and label exclusion remain
fixed. Scopes and heading-index statistics can change only as a consequence of
new detections. Existing generic-title/table-label and statement-prose false
positives remain. The shared scope assembler preserves section v1 behavior and
its original policy SHA. All 2,620 saved S1 source contexts reproduce exactly
in a source-only cache check; S2 pilot ranking and metrics have not been run.
Conservative source misses remain, including split numbering/title lines in
Best Buy 2019 and the unchanged false contents reset at Best Buy 2015 p74.

The comparison requires the saved native, expansion and S1 run lineages and
hashes, reproduces all four historical full-ranking controls and S1 score
components/context/metrics, and saves S2 outputs before parsing evidence labels.
It verifies exact unchanged body scores, evaluates S2 against both S1 and E,
and records paired gains/regressions, deeper gold-page ranks and the five
multi-page questions. New artifacts are immutable and outside Git. The suite
has 123 passing tests; actual Windows PowerShell/pilot execution remains pending.

This is the last planned heading-format ablation. After verifying real outputs,
recommend one retrieval baseline to freeze using primary Recall@5, complete
coverage, paired regressions and incremental cost; do not select on MRR alone.
If valid new headings yield no useful coverage advantage, favor expansion v1
and record detector/matching/selection limits without another heading repair
round. Any selection is development-only, not held-out evidence.

Then follow roadmap phases 2–4: freeze cohort/retrieval, pin and inspect rendering,
smoke-test one OCR engine (gold evidence pages only as an oracle diagnostic),
cache complete-report OCR with source-page/failure accounting, and compare
matched OCR/native retrieval under the frozen policy. The current render-pages
command is evidence-only; full-report rendering must be implemented for that
comparison. Answer extraction, ledger memory and held-out studies remain later
separate stages; native text/evidence snippets are not full transcription ground
truth and no OCR accuracy/cost/energy result is established by this patch.

## Verified final note-format results and retrieval recommendation (2026-10-12 EDT)

The researcher supplied complete run `20261013T030434Z-320eab2ccfc7` from folder
`note-formats-20261013T030434Z-7541d0a1`, exit code 0, after 123 local tests passed.
All 13 output hashes/sizes and 25 original/expansion/S1 input identities verify.
Executed source fingerprint matches the delivered note-format implementation
with Windows CRLF, on base 7ebb8f5 plus applied patch. Both 2,620-page source
contexts and all 120 full rankings reproduce; independent BM25 verifies 26,195
page scores (maximum absolute discrepancy 7.105427357601002e-15). Independent
rank/set arithmetic confirms all metrics, paired deltas and five-question subgroup.

Read docs/NOTE_FORMAT_RESULTS.md. S2 note formats improves Recall@1/3 to
14.58%/36.81% versus E/S1 10.42%/32.64%; MRR is 0.3470729345497992 versus
0.3024075204503773/0.31477955742883584. Recall@5 remains 40.97%, Hit@5 12/24,
complete coverage 8/24, and all 24 annotated top-five sets are unchanged.
All five multi-page tasks remain incomplete: subgroup Recall@5 36.67%, Hit@5
4/5, Complete@5 0/5. Their S2 gold ranks are identical to S1.

Against S1, Best Buy acquisitions p50 improves 4→1, Boeing legal p112 21→14,
and Boeing cyclicality p7 29→28; no gold ranks regress. Against E, first-gold
ranks improve for 11 questions, regress for 1 and stay fixed for 12. The
remaining regressions are AMD revenue change p42 7→8 and Boeing customer p7
39→46/p13 161→162; these already occurred in S1. At k=1 acquisitions supplies
the gain against E/S1; at k=3 the gain against S1 is acquisitions and the gain
against E is the earlier AMD quick-ratio change. No new top-five evidence is found.

Source repair is established: bare acquisition/restructuring boundaries and
the en-dash legal heading/one-page continuation reproduce. S2 adds 39 en-dash
headings and 17 accepted bare notes, changes 57 page contexts and retains the
64-token cap. Context contains 14,887 tokens on 1,667 pages. Known conservative
split-note/false-contents limitations and generic/prose false positives remain.
Correct note detection does not resolve vocabulary or multi-statement selection.

The single run records 3.067642 s total including reproduction/validation/scoring;
S2 context construction 0.999540 s versus S1 0.698179 s, and E/S1/S2 query
totals 0.016589/0.031507/0.029583 s. These are descriptive fixed-order logs,
not repeated latency, standalone pipeline cost or energy measurements.

Recommend carrying forward the already frozen **expansion v1** as the matched
native/OCR retrieval baseline at the predeclared five-page budget. Preserve
docs/EXPANSION_V1_CONTROL.json unchanged; the recommendation record is
docs/RETRIEVAL_BASELINE_RECOMMENDATION.json. S2's smaller-cutoff/MRR benefits
are real but do not improve primary/complete evidence coverage; keep S2 as the
completed structural comparator. This is an exploratory development choice,
not demonstrated held-out superiority. No executable policies change here.

The planned heading-format series is complete. Next implement full-report
resumable rendering (existing render-pages is evidence-only), verify/pin one
OCR adapter and inspect representative pages plus the 25 unique evidence pages
as an oracle diagnostic. Then cache complete-report OCR and compare matched
OCR/native retrieval under frozen E. Preserve cohort/PDF hashes, source IDs,
full candidates, minimal queries and failure accounting. Choose/freeze resolution
after the documented 200/300-DPI smoke inspection; hardware/runtime/checkpoints
and OCR results remain pending. Keep answer extraction, ledger and held-out
evaluation separate; no further heading-format tuning is planned.

## OCR setup continuation and accepted retrieval freeze (2026-10-12 EDT)

Continue from pushed bb274db5436473984456c1e95e30b1407337c1c4. The researcher
explicitly freezes expansion v1 for matched native/OCR retrieval at k=5 and closes
heading-format tuning. Existing expansion/stopword/BM25 policy snapshots and
historical controls are unchanged. The recommendation record now records that
accepted freeze; it remains offline documentation, not a runtime label input.

Read docs/OCR_SETUP_WINDOWS.md. First run scripts/check_ocr_machine.ps1 on the
actual Windows machine: GPU/VRAM/driver, Python installations/current baseline
version, physical/available RAM and free disk are **pending local measurement**.
Historical hardware labels and the hosted development machine are not current
local measurements. The inventory does not install dependencies and saves a
baseline package fingerprint for a later unchanged-environment check.

New finocr render-reports and scripts/run_report_rendering.ps1 implement
source-only full-report Poppler RGB rendering with original-native PDF/cohort
identity checks, zero-based physical IDs, every report/page including blanks and
exhibits, atomic per-page cache records, failed/pending accounting and verified
resume. A first/middle/last source-only sample preserves the complete 2,620-page
plan; sample_complete is distinct from full_report_rendering_complete. Proposed
200/300 DPI settings require visual/disk inspection before resolution is frozen.
The old evidence-only render-pages command remains separate and unchanged.

New finocr ocr-smoke prepares one source-selected page under standard PaddleOCR
with explicit local detector/English-recognizer weights, raw JSON/line boxes,
literal text and unchanged search normalization. The proposed separate 64-bit
Python 3.12 .venv-ocr uses CPU PaddlePaddle 3.3.0, PaddleOCR 3.3.2 and PaddleX
3.3.10; dependency resolution and real API execution are pending. Commands are
provided before installing anything. Do not modify the baseline .venv, install
CUDA/GPU packages before inventory review, or assume an RTX-3060 label specifies
VRAM. Preserve model hashes and the successful Windows dependency/wheel snapshot.

Setup observations, source rendering, a one-page nonempty OCR smoke and fixture
tests do not establish OCR accuracy, full-report throughput or retrieval results.
No QA/evidence input is accepted by the renderer/OCR engine. The smoke has a
process deadline and explicit failures/blanks and never claims full OCR coverage.
After local setup/source/numeric inspection, proceed to clearly labeled oracle
diagnostics and complete-report OCR before matched frozen-expansion retrieval.
No new corpus run or experimental metric is reported by this implementation.
The 138-test suite includes real small PDF rendering fixtures and simulated
OCR orchestration, with no downloaded/inferred model in development. Actual
PowerShell/Windows renderer/model execution remains pending local setup outputs.

## Full-report OCR implementation and recovered-workspace validation (2026-10-17)

Continue from pushed `61a696d9ca7dd0c505b1de662ca3eaea57ed3e9d`. The supplied
full-rendering records reconcile all 12 reports and 2,620 zero-based physical
pages at 200 DPI. The pinned CPU smoke's artifact hashes, raw/normalized output,
runtime and source image identity verify. Read docs/OCR_SETUP_REVIEW.md for
identities, observed setup timings and limits: original PDFs, all rendered PNGs
and model weights were not uploaded, and the old rendering wall time is only
the last resume invocation. Baseline preservation was reported by the researcher;
the next guide records a fresh independent before/after inventory pair.

The recovered implementation now provides resumable full-report CPU OCR using
the existing .venv-ocr and local model bundle. Per-report workers reuse model
initialization. Immutable attempts retain raw results, line boxes/confidences,
source/model checksums and explicit timeout/failure/interruption records.
Atomic commits rebuild the aggregate after a crash. Resume verifies condition,
code/runtime, source images, model files and previous results; completed/blank
pages are reused, failures retried and prior attempts preserved. Full cohort
records remain present during diagnostics and interruptions, with pending pages
explicit. No PDF or baseline dependency is changed.

The source-only financial-table selector previews eight pages across the four
2015 reports. It reads no QA labels. Inspect local OCR on those tables before
extending the same cache to all reports. Approximate numeric-token overlap is
an inspection aid, not transcription or financial-accuracy ground truth.

Matched native/OCR retrieval keeps frozen expansion v1 at primary k=5 with
unchanged questions, scoring, tokenizer/stopwords, query expansion, full-report
candidates and deterministic zero-based ties. Native full rankings/scores and
expanded queries reproduce before evidence labels are parsed; both predictions
are saved before evaluation. Answers/justifications/evidence labels never enter
OCR or indexes. Blank/failed pages remain empty-text candidates. Pending,
diagnostic and interrupted caches cannot supply full-pilot scores; final partial
caches with all pages accounted for are explicitly failure-inclusive.

Outputs report coverage, cumulative OCR attempts/retries and descriptive timing,
paired evidence gains/losses/ranks, and all five multi-page questions' completeness.
No OCR result or gain/regression is established by implementing that reporting.
The latest reporting edits pass all 16 feature tests; the full 157-test suite
passes with no skips on Linux, including real small rendering fixtures and
simulated OCR workers. Windows execution of the new wrappers, financial-table
quality review, full-report OCR and matched retrieval remain pending local
execution and verification of real outputs. No CER/WER, answer, energy or
held-out result is claimed.

Read docs/FULL_OCR_WINDOWS.md for exact no-install PowerShell commands and
recovery/resume steps. The final cumulative patch is against 61a696d and includes
all required files. The earlier full-ocr-recovery.patch is preserved unchanged
as a work-in-progress checkpoint; its status document remains historical.

## Isolated second-machine GPU support (2026-10-17)

The researcher reports Windows 11 Education 10.0.22000, Ryzen 5 PRO 5645,
16 GB RAM, RTX 3070 Ti 8 GB, driver 537.70, Python 3.13 only and 563 GiB free.
Official Paddle's cu118 index supplies a 3.3.0 Windows CPython 3.12 GPU wheel;
NVIDIA's CUDA 11.8 Windows toolkit driver requirement is 522.06, below 537.70.
Add Python 3.12.10 x64 per user to match the CPU reference, without replacing
3.13. Keep PaddleOCR 3.3.2/PaddleX 3.3.10 and non-framework CPU dependency pins.
Read docs/GPU_OCR_WINDOWS.md for official sources and exact staged commands.

The incremental patch applies over 61a696d plus full-report-ocr-final.patch on
the second machine only. Do not update the first machine while its CPU run
continues: source fingerprint is part of resume validation. Existing CPU
wrappers, frozen retrieval policies, model bundle and recovery checkpoint stay
unchanged. GPU uses .venv-ocr-gpu and a separate cache; only device and required
runtime differences change. Actual GPU/compiled CUDA checks reject CPU fallback;
timing synchronizes around GPU prediction. FP32 and all OCR parameters stay fixed.

The retained CPU diagnostic ad4cddfa7ac7489b8839275df9baf870 verifies all eight
nonempty page attempts, manifest artifacts, full 2,620-page source plan and eight
uploaded PNG hashes. Its selection is reused exactly. A source-only comparator
validates CPU/GPU lineages and attempts, then reports per-page raw/normalized text,
line order, polygons/confidences, numeric-token differences and separate page,
startup and invocation timing. Equal number sets do not establish table accuracy;
cross-machine timings are descriptive, not a device-isolated speedup estimate.
No questions, answers or evidence labels enter this diagnostic.

The complete suite is now 171 passing tests, including 14 new simulated device,
cache-isolation, synchronization and comparison cases. Windows runtime and test
execution, eight-page GPU OCR, manual inspection and CPU/GPU comparison remain
pending local outputs. The comparator deliberately leaves a full-GPU recommendation
pending manual/artifact review. No new GPU experimental result is reported here.

## Verified completed native/CPU-OCR/GPU-OCR pilot (2026-10-18)

The four supplied full-cache/matched-retrieval archives are now independently
verified. Read docs/NATIVE_OCR_PILOT_RESULTS.md and its JSON record. This
supersedes the dated pending-run statements above; it does not alter OCR,
retrieval, source PDFs or the frozen expansion v1 policy/control.

CPU run ad4cddfa7ac7489b8839275df9baf870 and GPU run
2ceb1dc5ae404c01b65e7128ea5afb3b each account for all 12 reports and 2,620
zero-based physical pages: 2,615 nonempty and five explicit blanks, no failures,
pending pages or retries. All 5,240 immutable page commits/raw normalizations,
118 manifest-listed artifacts and 32 successful worker sessions reconcile.
Source/render/model identities match across conditions. Actual PDF/image/model
bytes are not all included in these four archives; recorded lineage is verified.

Independent query-expansion, token counting, BM25 and label/set arithmetic
reproduce all saved full rankings/metrics and the historical native E control.
There are 15,717 independently computed scores across 72 unique rankings;
maximum absolute discrepancy is 7.105427357601002e-15. Primary Recall@5 is
40.972222%, Hit@5 12/24 and Complete@5 8/24 for native, CPU-OCR and GPU-OCR.
All 24 tasks recover the same annotated top-five evidence sets, with no
Recall@5 gain/regression. OCR Recall@1/3 is 8.333333%/24.305556% versus native
10.416667%/32.638889%; MRR falls 0.3024075204503773 -> 0.26647403541841813.
Three overall top-five page sets and seven top-five orders change. All five
multi-page tasks remain incomplete: Recall@5 36.666667%, Hit@5 4/5, Complete 0/5.

CPU/GPU raw text differs only at AMD 2022 p29 (period), Best Buy 2019 p99
(leading empty line), PepsiCo 2019 p107 (slash/em dash) and PepsiCo 2022 p255
(period). Raw/search strings match on 2,616/2,617 pages; all 2,620 indexed token
multisets and all CPU/GPU scores/ranks match. None of the four pages is selected
at k=5; all 24 ordered CPU/GPU top-five raw-text packets match exactly. The
slash/dash cell's financial/source meaning is not established by token equality.

Cumulative recorded OCR wall time, including the diagnostic, is CPU
65,903.791720 s and GPU 1,163.585884 s. Both retain two invocations, 2,620
attempts and 16 model initializations. The observed ratio 56.6385 is descriptive,
not a randomized device-only speedup or an energy/corpus-throughput claim.
Rendering retains only its last invocation time. Shared dependency versions
match; GPU-only NVIDIA packages and htcondor are explicitly recorded. The CPU
run's source matches the delivered CPU patch, while GPU sources match committed
3d0fc59 under Windows CRLF; earlier OCR runs recorded 61a696d plus working edits.

Next follow docs/BOUNDED_ANSWER_EXPERIMENT.md: one fixed compact text generator,
saved k=5 packets, deterministic bounded packing and isolated generation runtime.
Propose at most 48 distinct primary requests for 72 logical N/C/G records because
identical CPU/GPU requests can share a completion; at most 24 annotated-page
diagnostics follow sealed primary predictions. Freeze the private scoring key
before generation. Separate numerical extraction/units/sign/year/formula/arithmetic,
financial interpretation and citation support. All 24 remain in task denominators;
facet scores use their own predeclared eligible subsets. No new OCR/retrieval
tuning, new answer result, CER/WER, training or held-out claim is introduced.

This is a documentation-only patch against 3d0fc59. Runtime code, dependencies,
all executable policies and docs/EXPANSION_V1_CONTROL.json remain unchanged.
