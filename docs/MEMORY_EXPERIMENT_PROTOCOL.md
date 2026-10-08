# Proposed FinanceBench context and memory experiment

Status: design prepared on 2026-10-05; no OCR, retrieval, memory, or model-adaptation
benchmark has run. This protocol supersedes the earlier FinLongDocQA experiment
direction. Numerical budgets below are starting proposals to validate on development
data, then freeze; they are not demonstrated optima.

## Research question and contribution

Can section context and a bounded, source-linked memory improve financial evidence
retrieval and numerical extraction at a fixed inference budget?

The foundation is the multistage OCR/retrieval/compact-VLM approach in Han et al.,
https://arxiv.org/abs/2604.26462. The proposed contribution is a controlled evaluation
of reusable context under explicit memory and computation limits. Ordinary retrieval
already provides external memory: calling an index "memory" alone is not a novelty.
The experiment must isolate the incremental effect of the bounded context ledger.

The old one-shot versus pagewise OCR comparison is a possible secondary study.
Training from scratch, changing attention architecture, continual weight updates,
and generalization to all business documents are outside the first executable study.
Targeted fine-tuning remains an extension after a fixed-model baseline identifies
an error class worth learning. Model and hardware choices remain pending.

## Dataset, source authority, and splits

- Retain downloaded PDFs and upstream annotations unchanged under DATA_ROOT.
- Audit all supplied FinanceBench files; the expected complete release inventory
  from the project context is 368 documents and 150 public questions. The audit
  reconciles supplied versus retained records, but does not currently assert those
  fixed release totals. An apparently clean partial download is not a complete release.
- Scope the first experiment to metadata types 10k and 10k_annualreport. Exclude
  10-Q and earnings-release questions from this condition and record exclusion counts.
- Report annotation coverage by company, year, and selected report before selection.
- FinanceBench QA answers and evidence are task-specific supervision, not exhaustive
  page transcription or topic labels. Native PDF text is an approximate control;
  table reading order and text extraction require manual checks.
- Heading-derived section labels are weak labels until manually verified. Do not
  interpret a 10-K section pattern as ground truth for every page.

Start with approximately 8-12 annotated annual reports. Choose the actual cohort
only after coverage and page mapping checks. The existing earliest/middle/latest
12-report selector remains a longitudinal pilot, not the final held-out split.
Do not imply that it automatically contains enough QA for this experiment.

Assign all selected documents from a company to one group: development or held-out
evaluation. Select for sufficient question coverage without viewing model results.
Record the exact company rule, question counts, document hashes, and exclusions.
Do not enforce an arbitrary percentage split if it leaves too few evaluation cases.
If the cohort is too sparse, expand it before interpreting performance differences.

Development may be used for debugging, prompt choice, ranking weights, token budgets,
and manual correction. Evaluation labels and reviewer corrections are unavailable
to every tested component. Test PDFs may be indexed at test time as task inputs.
No test answers or justifications may enter prompts, indexes, or correction memory.
Any later training uses separate company groups; examples must not cross into the
evaluation group. Public-benchmark pretraining contamination is not ruled out by
this local split and must be acknowledged.

## Executable stages and comparison conditions

1. Audit input schema, files, page counts, evidence mappings, and source/retained
   record counts. Save diagnostics even if pilot selection fails.
2. Extract native PDF text for every page and run a page-level BM25 control.
   This develops the evaluation harness but does not constitute an OCR benchmark.
3. Render selected PDFs once with fixed settings. Cache OCR once for all conditions.
   Use one OCR engine and one fixed compact extraction model initially.
4. Evaluate conditions A, B, and C on identical questions and OCR outputs.

| Condition | Page retrieval and context | What changes |
|---|---|---|
| A: retrieval baseline | BM25 over all report pages; compact extraction from selected evidence | Reference pipeline |
| B: section context | Same index plus current section headings and heading-based ranking cues | Effect of explicit structure |
| C: bounded context ledger | B plus source-linked context retained during sequential ingestion | Incremental memory effect |

All three receive the same maximum final evidence budget and extraction prompt
format. Both B and C can access the same immutable full-page store. C is not allowed
additional gold evidence, a larger model, or a larger evidence context.
Log any model calls used to build context as part of C's ingestion cost.
Freeze ranking/fusion rules and tokenizer before evaluation.

Proposed initial final-evidence budget: at most 5 pages and 4,096 text tokens per
question, whichever is reached first. Reserve output capacity separately and
record truncation. Multimodal image-token and resolution limits must be defined
when the extractor is selected; text tokens alone do not bound visual computation.
Evaluate additional budgets only if time and annotation coverage permit.

## Bounded memory contract

The context ledger is an explicit data structure, not an assumed learned ability.
Reset it between reports. Traverse pages in PDF order during ingestion; do not use
later pages to annotate earlier ingestion events. Queries run after ingestion of
the complete report, so this first study is not a streaming QA benchmark.

Proposed initial limits: two recent pages available during context construction;
at most 32 older ledger entries and 1,024 total ledger tokens. Entries contain:

- document ID, company, reporting year, source page, and source span;
- detected section/heading and exact observed term;
- unit/currency/year context when present in that source span;
- optional inferred topic or term relationship, marked as a model hypothesis.

Source text and model inference must remain separate. Do not merge revenue, net
income, and sales solely because they are semantically related. Never overwrite
transcribed values with model guesses. A ledger entry is a pointer/context cue;
the cited page is the authority for extraction.

Prototype retention rule: keep recent entries, preserve an older entry only when
it adds a distinct section or term context, and evict the oldest redundant entry
first. Log every insertion, replacement, and eviction. Token and entry limits are
hard caps; implementation must expose its exact tie-break and overflow behavior.
Tune only on development data. Compare at least one smaller ledger budget if the
pilot is viable, to test whether any benefit depends on growth rather than policy.

External memory does not update model weights. A learned retention policy, LoRA,
or cross-year template reuse would be a separately identified experiment.

## Evaluation and cost accounting

Primary retrieval metric: macro evidence-page Recall@5 (fraction of annotated pages
retrieved per question, then averaged). Also report any-evidence Hit@5 and
all-evidence success separately: these are not interchangeable measures.
Report Recall@1/3 and MRR as diagnostics. Inspect annotation incompleteness before
calling every retrieved non-gold page irrelevant.

Extraction metrics: answer correctness, operand preservation for calculated answers,
unit/scale correctness, sign correctness, reporting-year correctness, and citation
support. Freeze scoring rules and numeric tolerances using development examples.
The current numeric_match helper ignores units/scales and must not serve as the
sole financial correctness evaluator. Subjective scoring needs a documented rubric;
do not assume string matching can score every FinanceBench answer.

Track total runtime, p50/p95 query latency, peak GPU memory where available, host
memory, OCR/context-building time, stored index/ledger size, final input/output
tokens, visual pages/regions, truncation, and failure/OOM counts. Include failed
runs in denominators; never report latency only for successful runs without saying so.

Separate initial ingestion from subsequent queries. Include OCR, indexing, context
generation, and any training time. Compare cost per supported correct answer using
explicit measured runtime and a stated hardware rental/accounting rate. Local
inference is not automatically free. Report the number of queries needed to amortize
extra ingestion work, if measurable. Do not claim a 1/1000 cost ratio in advance.

Energy requires measured power over time. GPU-only measurements must be labeled
GPU energy; whole-system measurements require a suitable meter or instrumentation.
If energy is unmeasured, report computation proxies without claiming energy savings.

Use paired question/document results; report denominators and confidence intervals
with resampling clustered by company when feasible. With very few held-out companies,
treat intervals and generalization claims as exploratory. A memory benefit must
be judged against its ingestion cost and the fixed evidence budget, not only accuracy.

## Readiness and deliverables

Before running: verify annotation coverage, freeze split manifests and settings,
manually check selected evidence pages, specify hardware/model versions, and validate
the numerical scoring rubric. The current audit's ready_for_native_text_baseline
status is only a structural starting gate, not completion of these research checks.

Deliverables: inventory/audit, cohort and split manifests, native-text control,
cached OCR pages, context/ledger event logs, condition outputs with citations,
paired evaluation table, cost breakdown, and documented failure cases.

Broader business-document generalization requires a later separately annotated
document-type dataset. Unseen company/year results demonstrate transfer within
annual financial reports, not to invoices or contracts.
