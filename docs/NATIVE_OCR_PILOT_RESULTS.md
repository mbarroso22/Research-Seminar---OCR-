# Verified native / CPU-OCR / GPU-OCR development pilot

**Verified 2026-10-18; documentation base `3d0fc59`.** The four supplied archives
contain completed full-report OCR and matched retrieval runs. This report replaces
the earlier pending-execution status. It does not change an executable condition.
The structured record is [NATIVE_OCR_PILOT_RESULTS.json](NATIVE_OCR_PILOT_RESULTS.json);
the proposed next study is [BOUNDED_ANSWER_EXPERIMENT.md](BOUNDED_ANSWER_EXPERIMENT.md).

At the frozen five-page budget, native, CPU-OCR and GPU-OCR all have **40.972222%
macro evidence Recall@5, 12/24 Hit@5 and 8/24 complete evidence coverage**. All
five multi-page questions remain incomplete. OCR loses smaller-cutoff performance
relative to native text. CPU/GPU have identical full retrieval scores and rankings,
despite four raw-text differences. This does not establish transcription or answer
accuracy, or equivalence on other queries/documents.

## 1. Scope and unchanged conditions

The fixed development pilot contains four companies, 12 reports, 2,620 physical
pages and 24 questions. Only six reports have annotated questions; all 12 are
processed/indexed. There are 25 distinct annotated evidence pages and 30
question/evidence-page references. The five multi-page questions and company/report
overlap make these dependent development observations, not held-out test results.
Upstream types remain 15 domain-relevant, four metrics-generated and five
novel-generated; those types are not numerical-versus-interpretive scoring facets.

All representations use frozen **expansion v1**, primary **k=5**, BM25
`k1=1.2, b=0.75`, binary query term frequency, the same Unicode-financial tokenizer
and stopwords, and full within-report candidates. Score ties retain ascending
zero-based physical page IDs. No section context, heading repair, OCR correction,
retrieval retuning or answer generation is introduced.

The query projection contains only `task_id`, `doc_id`, `question`. The executed
comparison code saves both complete prediction files before parsing evidence
labels. Answers, justifications and annotation evidence text are excluded from
OCR, indexes and queries. Labels are used offline for the checks in this report.
The 24-question file SHA-256 is
`1d1bfa444a3041b3e51be9535ff276fc89fa3d7985231a0bd7f4aa6746395356`;
the unchanged financial expansion policy SHA-256 is
`80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3`.
`EXPANSION_V1_CONTROL.json` remains byte-for-byte unchanged.

OCR uses the same source-derived 200-DPI RGB rendering, detector and English
recognizer files, FP32, thresholds, resizing, disabled orientation/unwarping,
disabled HPI/TensorRT/MKLDNN and two CPU threads. Device is `cpu` versus `gpu:0`.
Python is 3.12.10 x64 in both OCR environments; Paddle is 3.3.0 (CPU distribution
versus GPU distribution), PaddleOCR 3.3.2 and PaddleX 3.3.10. GPU workers record
CUDA 11.8 and actual GPU execution. Shared package versions match. The GPU
inventory additionally contains the NVIDIA CUDA 11 packages and `htcondor 25.10.1`;
the four archives alone do not establish the latter package's necessity/origin.
The full package differences are retained in the structured record.

## 2. Artifact identity and independent verification

| Supplied archive | Run ID | Manifest SHA-256 |
|---|---|---|
| `full-cpu-ocr-cache(1).zip` | `ad4cddfa7ac7489b8839275df9baf870` | `12a73c95b9d72a4100dd4c716c15705c42be5e6870b379b2b3b18273e0ee6d5e` |
| `full-gpu-ocr-cache(3).zip` | `2ceb1dc5ae404c01b65e7128ea5afb3b` | `c79e71c736ca6fe1f33d3fc7cdae039f212d01a094a209c3cd9eb17324afcf0d` |
| `native-cpu-ocr-retrieval(2).zip` | `2830eb7f969f44559e9dad1ddc82fd57` | `d49a871743eacb187f62339ed3788ca75bd9a37376c4a2b86401b8ad8f82a69c` |
| `native-gpu-ocr-retrieval(2).zip` | `856d76e60bc645cd9da9926232f83cb8` | `49b25103ac86366da493156e504ad6ca373a191301bd9425035d84978bd5b9e0` |

The JSON record also contains archive hashes/sizes and the source input identities.
Verification checked ZIP integrity, all 118 manifest-listed artifacts (51 per OCR
cache and eight per comparison), and all **5,240 immutable page commits** with
their request/raw/worker artifacts. Every committed raw result reconstructs the
stored literal text, ordered lines, confidences, polygons and search normalization.
Every source ID, page order, image identity, report checksum, device/configuration,
runtime, and attempt history reconciles. All 32 worker sessions initialized
successfully; each page has one committed attempt. No pending, failed, timed-out
or interrupted page is hidden by the final exports.

The rendering metadata snapshot is identical across conditions: run
`bdf1681af83144898dd05d469fbd1682`, manifest SHA-256
`1ff37ad01d37e3d961b3ae0d27805a1dde244023f7cd830c3bbab876c8c5ebce`.
The model-manifest identity is also identical, SHA-256
`d0a91a2378b843c0fcc3ea007e4505072277b55f3b6aa07ffab15c3af8a07cf4`.
These archives retain recorded identities rather than the complete PDF/PNG/model
bytes; this review verifies that binding, not a fresh physical rehash of those inputs.

The independent verifier uses standard-library token counts, explicit query-rule
matching, BM25 arithmetic, set intersections and reciprocal ranks. It does not call
the project's indexer or retrieval evaluator. It regenerates all 24 expanded
queries/audits and **15,717 page scores across 72 unique full rankings** (5,239
scores per representation). All page orders match; maximum absolute score
discrepancy is `7.105427357601002e-15`, below the frozen `1e-12` tolerance.
Both copies of native predictions in the current comparisons, and the retained
earlier expansion-v1 ranking control, reproduce. All 96 current prediction records
and saved aggregate/per-question/delta/evidence-rank calculations reconcile.
All 12 index sizes and average token counts reconcile in each representation.

Both comparisons identify the original native manifest
`5e4213b5e7e65a53e01e78352abeb039c6c79eac7a55c9c0999f304d4d114497`
and frozen expansion reference
`4eb18afc2eecc460cdd7b38b50773625ed8a59dfd862ada787395223b31bba63`.
Original native pages and the frozen task file were independently rehashed from
the previously supplied source cache, not reconstructed from evaluation snippets.

The OCR runs record `61a696d` plus working edits. Their actual Windows-CRLF
Python-source fingerprints match the delivered CPU implementation
`a408775060c340843c51f93f4dcc36f1ef3983bb70b421a21c31bd0d37593fad`
and committed GPU implementation in `3d0fc59`
`4008f049ffb362f49a40fb86f0946f077bef55e862e86aa4f85de14d2f5b80e1`.
CPU retrieval used the CPU source on Python 3.13.7; GPU retrieval records clean
commit `3d0fc599cfb3b7abae0c60761c5f31d5018e43fc` on Python 3.13.7.
Do not describe the earlier OCR runs as clean executions of that later commit.

## 3. Coverage, including blanks

| Report | Pages | Native blanks | CPU blanks | GPU blanks |
|---|---:|---:|---:|---:|
| AMD 2015 / 2019 / 2022 | 215 / 109 / 121 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Best Buy 2015 / 2019 / 2023 | 147 / 107 / 75 | 3 / 2 / 0 | 2 / 1 / 0 | 2 / 1 / 0 |
| Boeing 2015 / 2019 / 2022 | 174 / 144 / 190 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 |
| PepsiCo 2015 / 2019 / 2022 | 168 / 667 / 503 | 0 / 1 / 0 | 0 / 1 / 0 | 0 / 1 / 0 |
| Total | **2,620** | **7** | **5** | **5** |

Native has 2,613 nonempty pages; each OCR condition has 2,615. Both OCR runs are
`complete`, `full_ocr_coverage=true`, with zero failures/pending pages. The five
OCR blanks are Best Buy 2015 p95/p140, Best Buy 2019 p20, Boeing 2022 p59 and
PepsiCo 2019 p548. They remain candidates with empty search text. Best Buy 2015
p108 and Best Buy 2019 p99 are native-empty but OCR-nonempty; this is a coverage
observation, not proof of useful or correct transcription. Native emptiness is
not a ground-truth blank-page label.

## 4. Independently verified retrieval results

Recall is macro evidence-page recall over all 24 questions. Hit means at least
one annotated page is present; Complete means all annotated pages are present.
These metrics have different meanings and denominators from answer accuracy.

| Condition | Recall@1 | Hit@1 | Complete@1 | Recall@3 | Hit@3 | Complete@3 | Recall@5 | Hit@5 | Complete@5 | Full-ranking MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Native + frozen E | 10.416667% | 4/24 | 1/24 | 32.638889% | 10/24 | 6/24 | 40.972222% | 12/24 | 8/24 | 0.3024075204503773 |
| CPU-OCR + frozen E | 8.333333% | 3/24 | 1/24 | 24.305556% | 8/24 | 4/24 | 40.972222% | 12/24 | 8/24 | 0.26647403541841813 |
| GPU-OCR + frozen E | 8.333333% | 3/24 | 1/24 | 24.305556% | 8/24 | 4/24 | 40.972222% | 12/24 | 8/24 | 0.26647403541841813 |

Against native, both OCR conditions have **zero Recall@5 gains and zero
regressions: all 24 questions recover the same annotated top-five evidence sets**.
There are no no-match questions, extraction-failed questions or failure-inclusive
scores. All top-five scores are positive; the retained zero-score tie policy is
not responsible for these top-five hits.

Equal annotated coverage does not mean identical retrieved context. Three
questions change their overall top-five page sets: Best Buy inventory `04417`,
acquisitions `01077` and cash-flow comparison `01275`. Seven top-five orders
change. The first annotated page moves closer for three questions, farther for
seven and remains fixed for 14. In the table below, short IDs abbreviate
`financebench:financebench_id_...`; every rank is one-based, while page IDs stay
zero-based.

| Task / subject | First gold rank native -> CPU/GPU | Effect |
|---|---:|---|
| `03069` AMD D&A margin | 1 -> 3 | Loses the k=1 hit; retains the k=3/5 hit |
| `01198` AMD revenue drivers | 7 -> 8 | Deeper-rank regression; still misses k=5 |
| `00917` AMD operating-margin driver | 3 -> 4 | Loses k=3 complete coverage; keeps k=5 |
| `04417` Best Buy inventory | 13 -> 16 | Deeper-rank regression; still misses k=5 |
| `00685` Best Buy margin consistency | 29 -> 27 | Improvement outside k=5 |
| `01077` Best Buy acquisitions | 3 -> 4 | Loses k=3 complete coverage; keeps k=5 |
| `00517` Boeing revenue categories | 97 -> 96 | Improvement outside k=5 |
| `00464` Boeing cyclicality | 31 -> 32 | Regression outside k=5 |
| `00585` Boeing effective tax rate | 30 -> 31 | Regression outside k=5 |
| `01009` PepsiCo geographies | 20 -> 19 | Improvement outside k=5 |

The structured record preserves all 24 questions' evidence ranks and top-five
pages, including deeper movements that do not change first-gold rank. The
observed losses at k=1/3 and MRR must not be omitted because primary k=5 ties.
No additional tuning is justified or performed as part of this results update.

## 5. All five multi-page questions

CPU and GPU ranks below are identical. Each cell lists `physical page: rank`.

| Task / subject | Gold pages | Native ranks | CPU/GPU ranks | Recall@5 native / OCR | Complete@5 |
|---|---|---|---|---:|---:|
| `03069` AMD 2015 D&A margin | 55, 59 | 55:25; 59:1 | 55:41; 59:3 | 0.5 / 0.5 | 0 / 0 |
| `01290` Boeing 2022 customers | 7, 9, 13 | 7:39; 9:3; 13:161 | 7:39; 9:3; 13:161 | 1/3 / 1/3 | 0 / 0 |
| `01009` PepsiCo 2022 geographies | 3, 4 | 3:228; 4:20 | 3:229; 4:19 | 0 / 0 | 0 / 0 |
| `03620` PepsiCo EBITDA less capex | 61, 63 | 61:23; 63:1 | 61:22; 63:1 | 0.5 / 0.5 | 0 / 0 |
| `04481` PepsiCo EBITDA margin | 61, 63 | 61:24; 63:1 | 61:25; 63:1 | 0.5 / 0.5 | 0 / 0 |

For every condition, subgroup macro Recall@5 is **36.666667%**, Hit@5 **4/5**,
and Complete@5 **0/5**. Recovering one financial statement cannot establish that
both numerator and denominator or all required operands were available. Conversely,
annotations may be incomplete: absence of a labeled page does not by itself prove
that an answer is impossible from an alternative retrieved source. The next study
must judge the actual packed context and answer support.

## 6. Four CPU/GPU text differences

| Zero-based source page | CPU text | GPU text | Search/index effect |
|---|---|---|---|
| AMD 2022 p29 | Sentence ends `our business.` | Ends `our business` | Search strings differ; indexed token counts identical |
| Best Buy 2019 p99 | Leading empty line before `FSC* C0112076` | Leading empty line absent | Search strings identical after whitespace normalization |
| PepsiCo 2019 p107 | A standalone `/` near `Special termination benefits` | A standalone em dash `—` | Search strings differ; both glyphs are omitted by the frozen tokenizer |
| PepsiCo 2022 p255 | Definition ends `Section 409A.` | Ends `Section 409A` | Search strings differ; indexed token counts identical |

Thus **2,616/2,620 raw strings**, **2,617/2,620 search strings**, and
**2,620/2,620 indexed token multisets** match. Identical token counts imply
identical report lengths, document frequencies and BM25 scores for this tokenizer;
independent recomputation also confirms exact CPU/GPU saved score/rank equality.
This is not a statement that punctuation, signs or line geometry are always
irrelevant to financial interpretation. The slash/em-dash cell needs source-image
inspection to determine which transcription is faithful; do not silently label
one as a correction, zero, missing value or equivalent financial meaning.

None of these four pages appears in any pilot top-five OCR packet. The ordered
page IDs and literal raw page texts in **all 24 CPU/GPU top-five packets are
identical**. Consequently a fixed deterministic packer produces duplicate
CPU/GPU answer prompts. Confidence differences are not answer-model inputs in
the proposed text-only experiment. Full raw JSON/confidence/geometry identity
across all pages is not claimed.

## 7. Timing and cost observations

All values below are recorded seconds, independently summed from attempts,
sessions or invocation histories. Each OCR condition has two invocations:
eight diagnostic attempts, then 2,612 new full-run attempts. Successful diagnostic
pages were reused. There are 2,620 attempts and 16 successful initializations
(four diagnostic reports plus 12 report workers in the full invocation), with
no retries or unknown-duration attempts/invocations.

| Recorded quantity | CPU | GPU |
|---|---:|---:|
| Diagnostic invocation wall | 205.107330 | 70.552244 |
| Full-extension invocation wall | 65,698.684390 | 1,093.033639 |
| Cumulative invocation wall | **65,903.791720** (18 h 18 m 23.79 s) | **1,163.585884** (19 m 23.59 s) |
| Page-attempt wall, excluding startup wall | 65,699.258869 | 924.069682 |
| Worker inference + serialization | 65,520.549243 | 747.876713 |
| Worker startup wall | 112.273475 | 131.089627 |
| SDK model initialization | 107.281052 | 126.499539 |

GPU prediction timing synchronizes device work before and after prediction.
SDK observations overlap their parent wall measurements; do not add these table
rows together. The cumulative wall-time ratio is descriptively **56.6385 CPU/GPU**,
not a causal device-only speedup. Hardware/load, wall-time order, warmup and
cross-machine execution were not randomized or repeated; energy and peak
RAM/VRAM were not measured by these artifacts. Do not infer corpus-wide throughput,
power savings or per-correct-answer efficiency from the ratio.

| Matched retrieval run | Native index | OCR index | Native queries (24) | OCR queries (24) | Total including verification/evaluation |
|---|---:|---:|---:|---:|---:|
| CPU comparison | 0.544410 | 0.484304 | 0.017955 | 0.018172 | 21.316940 |
| GPU comparison | 0.541771 | 0.491597 | 0.019481 | 0.018782 | 20.977537 |

Retrieval runs index native then OCR in fixed order. These are single-run
descriptive logs, not repeated latency estimates. Original native extraction
records 88.410912 s. Shared rendering records 1,076.352844 s for its last retained
invocation only, across a two-attempt rendering history; cumulative rendering
cost is unavailable. Do not count that value as complete ingestion cost or charge
the same shared rendering separately to both OCR conditions.

## 8. Interpretation, limitations and next decision

This pilot establishes operational full-report OCR, reproducible matched
retrieval, and equal CPU/GPU retrieval inputs under the frozen tokenization.
It does not show improved primary retrieval relative to native text. The five
multi-page failures and the smaller-cutoff OCR losses remain visible. Preserve
native expansion v1 as the control and retain both immutable OCR conditions.
Use the completed GPU cache for the next OCR-text answer packets rather than
rerunning OCR; it is text-identical to CPU within every selected packet.

Limitations that constrain the claims:

- This is a label-exposed, deliberately selected development cohort: 24 questions
  from six annotated reports, four companies and uneven question types. It is not
  a company/document hold-out and gives no generalization or significance claim.
- Native PDF text is not full transcription gold. Clean rendered annual reports
  are not equivalent to the paper's private scanned KYC documents. No CER/WER or
  full-table numerical/structural accuracy has been measured.
- The four archives contain raw OCR outputs and rendering/model identities, not
  all original PDFs, image files or model weights. Eight earlier diagnostic PNGs
  were separately checked; that is not a new visual review of all 2,620 pages.
- Completion includes explicit blanks; absence of engine failures is not content
  correctness. Minimal query records and reviewed source fingerprints support
  label exclusion; artifact review does not instrument every runtime memory read.
- Equal bag-of-token indexes and evidence Recall@5 do not imply equal table order,
  punctuation semantics, available operands, supported answers or interpretation.
- The pilot contains no generated answers, unit/sign/year-aware correctness scores,
  financial interpretation scores, answer calibration, measured energy or training.

Proceed to one bounded, text-only answer-generation/correctness pilot using the
saved rankings and immutable page text. Separate numerical correctness from
interpretation and support, and distinguish missing retrieval evidence from
packing, OCR, extraction, arithmetic and reasoning errors. The next protocol
proposes that experiment; it is not executable or a completed result. No new OCR,
retrieval or heading-format tuning is planned here.
