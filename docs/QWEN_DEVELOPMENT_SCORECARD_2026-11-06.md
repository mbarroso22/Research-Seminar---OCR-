# Qwen development scorecard and next comparison

Reviewed 6 November 2026. Retrospective development adjudication; not a held-out benchmark or an official FinanceBench score.

## Result

Six questions were answered twice: once using five semantically retrieved native-text pages, and once using the annotated evidence pages (oracle). Reference answers and justifications were not included in either prompt. All 12 requests completed. Execution success is separate from answer quality.

| Question ID suffix | Task | Retrieved | Oracle | Adjudication |
|---|---|---|---|---|
| 01148 | Amcor industry | Fail | Pass | Retrieved output was empty despite relevant evidence being present. Oracle identified packaging. |
| 07966 | Activision three-year capex/revenue | Pass | Pass | Final 1.9% agrees with the reference and recomputed arithmetic. |
| 02981 | Corning three-year operating margin | Pass | Pass | Final 10.3% agrees with the reference and recomputed arithmetic. Oracle has an intermediate percentage-notation error. |
| 00790 | CVS capital intensity | Fail | Fail | Both say No; benchmark says Yes. Oracle extracts genuine balance-sheet numbers but uses a narrower physical-assets interpretation. Retain an ambiguity flag. |
| 03882 | Amcor FY2020 net receivables | Pass | Pass | Original statement shows $1,615.9 million. Benchmark gives $1,616.00 million. Accept source precision because the question does not require whole-million rounding. |
| 00070 | American Water Works working capital | Fail | Fail | Retrieved answer lacks necessary current-assets evidence but still asserts No. Oracle computes −$1,561 million correctly but opens with Yes/positive and later contradicts it. |

**Answer-level development result: retrieved 3/6 (50%); oracle 4/6 (66.7%).** This counts correct central answers, not flawless explanations. Do not infer a reliable population difference from six paired cases.

## Source-page adjudication

Five exported original-page images were visually inspected. Indices below are zero-based physical PDF indices, not printed page numbers.

- Amcor 2020, index 49: Trade receivables, net = 1,615.9 in the 2020 column; statement units are millions. This resolves the reference-rounding discrepancy in Qwen's favor.
- American Water Works 2022, indices 80–81: total current assets = 1,250; total current liabilities = 2,811, both millions. Difference = −1,561. The reference answer is supported, but its supplied justification expression, 334+114+275+98+312−254−706−49, equals +124 and does not establish that answer. Preserve the original reference and record this discrepancy separately.
- CVS 2022, index 107: net income = 4,165 (2022) and 7,898 (2021), millions. Index 109: total assets = 228,275 and 232,999; 2022 property/equipment = 12,873. Reference ratios reproduce approximately 1.82%, 3.39%, and 5.64%. These figures support the reference's arithmetic, but do not remove the interpretive ambiguity in the phrase capital-intensive. Both responses remain benchmark disagreements; report this case separately rather than silently replacing its label.

The Activision, Corning and Amcor industry original-page images were not included in this five-page export. Their adjudications use the saved prompts, reference records and arithmetic checks; do not describe every source PDF as visually verified.

## Scoring rules for the next comparison

These rules were developed after reviewing Qwen outputs. Fix them before reviewing another model's answers, and label the resulting comparison developmental.

1. Evaluate the entire response for a clear central answer, correct entity/period/units and material contradictions. A correct number buried beneath a contradictory Yes/No does not pass.
2. Accept a source-verified precise value when the question specifies no conflicting rounding requirement. Record reference discrepancies without changing the original benchmark data.
3. For explicit rounding requests, calculate with unrounded intermediate values and assess the requested final precision. Do not use a blanket percentage tolerance.
4. Score evidence support, citation correctness, arithmetic presentation and unsupported claims separately from central-answer correctness. A pass is not a certification that every sentence is correct.
5. Empty output fails. Appropriate abstention is recorded as safe behavior but does not count as a correctly answered benchmark item. Missing information in retrieved pages must not be asserted absent from the entire report.
6. Keep interpretive or defective-reference items in the complete results with flags, and report a predeclared sensitivity analysis excluding flagged items. Apply identical rules to every model.
7. Preserve all attempts, errors, timeouts and truncations. Do not choose the best of repeated generations after seeing results.

## Next experiment

First compare a stronger reference model on the same six questions and the same two evidence conditions (12 requests). Preserve the exact system instruction, question wording, page text and page order. Translate the saved Qwen chat wrapper into the provider's system/user message format; do not send Qwen control tokens as document text. Keep gold answers and justifications outside inference inputs.

Record the exact model/version, provider, date, supported generation settings, input/output tokens, finish reason, latency and billed cost. Model tokenizers differ, so report provider token counts rather than claiming identical token counts. Preserve equivalent response limits where possible and document any API differences. Use a fixed spending ceiling before launching paid requests.

Review model-anonymized answers against the same rubric. This separates interpretation/generation differences from retrieval differences. It is not a full-document comparison and does not establish frontier equivalence.

Then use the observed failure categories to choose one application improvement: missing evidence → retrieval/context expansion; evidence present but wrong response → answer generation/consistency; damaged table/chart evidence → targeted visual processing. Keep the original outputs unchanged and evaluate the change in a separate run. Later confirm on a fresh, independently reviewed set.

Do not rerun completed OCR, embeddings or the larger retrieval study. Full-document generation, a stronger-model run, earnings-call data collection and a visual parser experiment remain unfinished.

## Configuration and provenance

Qwen3-4B-Instruct-2507, local Q4_K_M, llama.cpp b6500/a7a98e0f, Windows/Vulkan, RTX 3070 Ti 8 GB. Context 16,384 tokens; maximum output 1,024; temperature 0; seed 0; no context shifting. Native text only. No vision input in these Qwen runs.

- Six-question run ZIP SHA-256: c69e0e73e89d0f6bf11d19f3753ae7e2cc44bd18639f241bb0b6eaf0ddd2eb7c
- Source-page review ZIP SHA-256: 81570eb14017d771d3d48e23d58403c91f54cb98e167d9097870a28121ef7e86
- All five PNG hashes matched the exported page identities. Recorded source PDF hashes matched the frozen cohort manifest; this comparison is not a fresh local hash of the Windows source PDFs.

The larger exploratory study remains complete: 20 companies, 43 reports, 7,003 pages and 58 questions. Its retrieval results are separate from these six answer-generation results. The original fixed hybrid development gate remains FAIL.
