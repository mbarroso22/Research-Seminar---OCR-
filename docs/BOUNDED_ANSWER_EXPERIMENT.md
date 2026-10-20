# Proposed bounded answer-generation and correctness pilot

**Design proposed 2026-10-18; primary generation/evaluation not implemented or executed.**
Feasibility setup and evaluator preparation now have a separate implementation:
[staged Windows guide](ANSWER_FEASIBILITY_WINDOWS.md) and
[preparation status](ANSWER_PREPARATION_STATUS.md). The pinned backend is a
setup candidate; the original synthetic execution is now reviewed separately in
[the synthetic review](SYNTHETIC_FEASIBILITY_REVIEW.md). The completed v2 FA-off
campaign is now [verified separately](SYNTHETIC_V2_REVIEW.md): 1/6 strict mechanical
compliance, budget exhausted. Contract repair and final private-rubric adjudication
remain pending. No benchmark answers have
been generated. This follows the
[verified native/CPU-OCR/GPU-OCR pilot](NATIVE_OCR_PILOT_RESULTS.md). It instantiates
the fixed answer-extraction stage of the roadmap, before any further context or
memory study. It changes neither OCR nor retrieval. Expansion v1, primary k=5,
the 24 questions, report/page scope and all saved rankings stay frozen.

## 1. Question and bounded design

Can one compact text-only generator produce numerically correct, correctly
interpreted and source-supported financial answers from the existing five-page
packets? Which failures occur before generation, and which occur in extraction,
calculation or interpretation after useful evidence is present?

Use one model, prompt, tokenizer, quantization, decoder and packer across:

| Logical condition | Immutable input |
|---|---|
| N-answer | Native raw page text at the saved native expansion-v1 top five |
| C-answer | CPU-OCR raw page text at the saved CPU expansion-v1 top five |
| G-answer | GPU-OCR raw page text at the saved GPU expansion-v1 top five |

This is the same 24-question development cohort, not a new held-out benchmark.
Run on one fixed answer-generation machine/backend, separate from the OCR device
conditions. Do not interpret C-answer/G-answer as different generator hardware.
No new OCR, retrieval, query, heading, formula-expansion, re-ranking or context
selection sweep is included. No ledger, fine-tuning, web search or VLM inputs.

**Original design budget:** at most six synthetic feasibility requests, at most 48 distinct
primary requests representing 72 logical condition/question records, and at most
24 separately labeled annotated-page diagnostic requests. Maximum 78 distinct
requests in this proposed pilot, each with one completion. No best-of-N selection
or answer-driven retries. Transport failures can be resumed without changing the
request; retain all attempts, charge them and never choose among successful outputs.

**Setup-only amendment, 2026-10-18:** the first six synthetic requests are exhausted
and retained, including their validation failures and unintended effective Flash
Attention setting. One separately sealed campaign permits at most **six additional
synthetic requests**, with no retries: cumulative synthetic ceiling **12**. It uses
the same fictional prompts/model/backend, strict v2 output grammar and explicit
verified FA off. See [the staged v2 guide](ANSWER_VALIDATION_V2_WINDOWS.md). Offline
audit/preparation spends zero requests. No primary or annotated-page generation
is authorized or implemented by this amendment. The future design allowances of
48 primary and 24 diagnostic requests remain unchanged; if separately implemented
and authorized later, the amended all-stage ceiling would be 84 rather than 78.
This does not erase the first six or permit answer-driven repeated campaigns.

**Completed-budget update:** both synthetic campaigns are now complete and the
12-request allowance is exhausted. Zero new inference is authorized. The
[next contract qualification](ANSWER_CONTRACT_NEXT_DESIGN.md) is an unimplemented
proposal only, contingent on offline conformance repair and a separately declared
new budget; it does not reopen either ledger or borrow future benchmark requests.

The reason for deduplication is verified input equality, not presumed model
accuracy. All 24 CPU/GPU ordered top-five raw-text packets match exactly; none of
the four changed pages is selected. After packing, hash the complete canonical
model request including prompt, model/revision, tokenizer/template, decoder and
budget. Reuse a single completion only when the full hashes match. Preserve
condition aliases and charged-versus-reused cost explicitly. Condition/device/cache
identities stay in provenance metadata outside the actual model request, so they
cannot prevent reuse of identical prompts or identify a condition to the model.
C/G answers will
then be identical by construction, not evidence from independent generations.
The primary paired comparison is N versus the unique OCR packet on 24 questions.

## 2. Feasibility and freeze before looking at generated pilot answers

Retain the roadmap's provisional text model
[`Qwen/Qwen3-4B-Instruct-2507`](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
as the first candidate. Its official card identifies a 4B, non-thinking text
model; the card was checked on 2026-10-18. The proposed 8-GB deployment is one
four-bit weight quantization, not a claim that the original BF16 weights plus
context fit the GPU. If a local conversion such as Q4_K_M is used, pin the
official base revision, conversion/quantizer commit and resulting file SHA-256;
do not describe a community or locally converted file as an official Qwen release.
The setup now pins llama.cpp b6500 and a locally converted Q4_K_M artifact. The
first six completions fit the recorded resource limits, but output validation
failed and FA was auto-enabled. V2 now completes with verified FA off/resource
checks, but only one response passes strict mechanics; overall feasibility fails.
Do not substitute another model during scored execution.

Use a new answer environment/model directory/cache. Preserve `.venv`, `.venv-ocr`,
`.venv-ocr-gpu`, all OCR outputs, source files and retrieval controls. Do not
install generation dependencies into an OCR environment or update the GPU driver
as an implicit part of this documentation proposal.

The original six synthetic requests, plus only the explicit six-request setup
amendment above, use fictional reports to check signed
amounts, unit conversion, percentages, arithmetic, narrative support/contradiction,
and insufficient evidence, including one request at the maximum input/output cap.
No FinanceBench question, answer, justification or evidence text is a prompt
example. Check actual peak VRAM/RAM, schema handling, runtime/device, OOM/deadline
behavior, chat template and retained request/output hashes. This is setup, not
pilot accuracy. If the bounded request does not fit, stop with feasibility logs
and revise the proposal before any primary answer is generated.

Freeze a manifest containing the exact model/tokenizer revisions and file hashes,
quantizer and backend commits, Python/dependencies, actual device, context/KV
configuration, prompt/schema, decoder, timeout, packer, task/query hashes and
retrieval/cache input identities. Proposed decoding is greedy, `do_sample=false`,
one completion, seed 0, batch size 1, maximum 1,024 generated tokens, 180-second
request deadline and model context capacity at least 6,144 tokens. Greedy decoding
is a reproducibility choice, not the model card's recommended sampling setup or
a guarantee of bitwise GPU determinism. Preserve raw outputs on every failure.

## 3. Input separation and deterministic packing

The primary generator accepts only the original `task_id`, `doc_id`, question,
and the five already-ranked source pages with zero-based page IDs and literal
`raw_text`. Do not give expanded retrieval terms, scores, gold page IDs, question
types/facet labels, reference answers, justifications, annotated evidence snippets,
manual corrections, OCR confidence/polygons, or prior model answers to the model.
Do not ask a reasoning model to supply missing facts from its pretrained knowledge.

Proposed packer `ranked-prefix-800-v1`:

Give the report ID once at packet level, then use compact page headers such as
`[p=55]` and compact truncation markers. Do not repeat long report identifiers in
every header; the actual complete evidence-token count is still enforced below.

1. Use the saved ranking's first five physical page IDs in rank order. No
   deduplication, page substitution, extra search, table reconstruction or
   answer/query-directed selection within a page.
2. Include each page's source header and the first at most 800 body tokens under
   the frozen answer-model tokenizer. Preserve the source line breaks represented
   by the retained token slice. Mark truncated pages explicitly. No redistribution
   of unused page capacity. Blank pages retain a header and explicit blank marker.
3. Body text is at most 4,000 tokens; the full evidence packet, including page
   headers and truncation markers, is at most 4,096. The remaining prompt/question/
   schema budget is at most 1,024; the fully rendered model input, including chat
   special tokens, is at most 5,120. Enforce the final tokenized count rather than
   adding estimates. A budget violation is a recorded failure, not silent dropping
   of a page or dynamic enlargement. Input plus maximum output is at most 6,144.
4. Save selected IDs, rank order, raw-page identities, exact prompt bytes/token
   IDs, retained token intervals, truncation flags and actual token counts. Hash
   canonical requests and map identical C/G requests to their shared completion.

The prefix cap is deliberately simple and may remove answer-bearing material.
Report the frozen pre-packing Recall@5 separately from packed-context availability.
For offline error review, inspect which required figures/claims survive packing;
those findings cannot alter the primary packer or trigger page expansion.

## 4. One fixed prompt and auditable output

Proposed instruction: answer only from the supplied report excerpts; obey the
question's fiscal period, metric definition, units and requested scope. Cite
zero-based source pages and concise literal support. For numerical comparisons
or calculations give the figures used, their units/years and a compact formula.
If required facts cannot be supported by the packet, return insufficient evidence.
Do not invent missing operands or treat a missing statement as a zero.

Require one JSON object with:

- `status`: `answered` or `insufficient_evidence`;
- `answer`: the final answer and brief justification;
- `claims`: concise factual/interpretive claims, each with source page IDs and
  short literal supporting spans;
- `quantities`: named operands/figures with raw value string, unit/currency/scale,
  fiscal year and source pointer; empty when inapplicable;
- `calculation`: named operand IDs, expression and final value/unit, or null;
- `missing_information`: explicit missing facts for abstentions, otherwise empty.

No hidden chain-of-thought is requested. The schema must fit the output cap for
the synthetic maximum-size case before primary execution. Invalid JSON, missing
required fields, timeouts, OOMs and output truncation remain failures in the
24-question denominator. There is no repair prompt or second answer attempt.
Save raw text even when parsing fails. An answered response requires valid cited
pages/spans from the exact packet; an abstention need not invent a citation.

There is **no calculator tool in this first generation condition**. Independently
recompute submitted expressions and the private expected calculation using
`Decimal` and a restricted arithmetic parser at evaluation. Never execute a model
expression with unrestricted `eval`. A later calculator-assisted generation study
would be a separately declared condition, not an invisible correction to this one.

## 5. Private scoring key: numerical accuracy and interpretation are separate

Before primary generation, prepare/freeze an evaluator-only rubric from the
original references and source PDFs. Do not use the generator to set its own
expected values, tolerance or interpretation checklist. Preserve raw upstream
labels and record source/reference discrepancies in a separate overlay, with
reasons and version/hash. Do not resolve an ambiguous reference after seeing the
answer in a direction that favors that answer.

The proposed question-based facets are nonexclusive and are not new official
FinanceBench categories. Short IDs below abbreviate `financebench:financebench_id_`.

| Proposed facet group | Short task IDs | Count / eligible axes |
|---|---|---|
| Direct numerical extraction/calculation | `03069`, `04417`, `01328`, `03620`, `04481` | 5; numerical axis |
| Mixed numerical comparison and interpretation | `00222`, `01279`, `00563`, `00757`, `00685`, `01275`, `00517`, `00678`, `01290`, `00585` | 10; both axes |
| Narrative/interpretive | `00995`, `01198`, `00917`, `01077`, `01091`, `00464`, `00494`, `01009`, `00735` | 9; interpretation axis |

This gives **15 numerical-facet questions** and **19 interpretation-facet questions**,
with ten shared. Comparative selection questions need the supporting figures used
to justify the selected activity/segment. Aircraft model IDs such as 737/787 are
identifiers, not financial quantities; a generic number-substring matcher is
inappropriate. Every condition retains all 24 questions for overall correctness.

### Numerical axis

Score separately: operand transcription/extraction, year/period, sign,
currency/unit/scale, metric/formula selection, arithmetic execution and final
numerical result. Require every requested component, not only the first number.
For instance, a tax-rate comparison must get both fiscal years and both signs;
an EBITDA definition must follow the question's operating-income/D&A definition
rather than substitute adjusted EBITDA. A correct final number with unsupported
or wrong operands is not a fully supported numerical answer.

Proposed normalization/tolerance policy, frozen per quantity before generation:

- Parse decimal strings, grouping commas, parentheses/Unicode minus and explicit
  units without discarding signs. Convert unit-equivalent values into the same
  currency/scale. A value with a missing/wrong required unit or fiscal period fails
  that facet even if its digits match.
- Use the question's stated rounding when present; otherwise use a predeclared
  source/reference display quantum `q`. Require matching rounding at `q` using
  the frozen decimal rounding rule; publish `q` and any boundary handling in the
  private rubric. Do not introduce a blanket 1% tolerance.
- Examples: one-decimal percentage answers use `q=0.1` percentage point (half-step
  0.05 percentage point); a two-decimal ratio uses `q=0.01` ratio unit; a two-decimal
  tax percentage uses `q=0.01` percentage point. An amount displayed in whole USD
  millions uses `q=1` USD million after scale conversion. These are proposed
  display-equivalence rules, not permission to ignore a wrong sign/scale/year.
- Distinguish percent from percentage-point change and a ratio from a percentage.
  A requested exact zero requires zero; no relative-error rule is applied at zero.
  Extra factual quantities asserted in an answer are also checked for contradiction.
- If references/source definitions conflict, flag the item before generation.
  Report unscorable counts and both the fixed cohort and eligible-facet denominators;
  never silently drop it or claim 15 scorable numerical items if fewer survive
  the predeclared source review.

Do not use the existing `numeric_match` helper as the primary evaluator: it does
not establish correct units, signs, fiscal periods, complete calculations or
financial meaning. Report final-number match and fully supported numerical
correctness separately to expose correct guesses or incorrect reasoning.

### Interpretation axis

Use a per-question checklist of required propositions, decision/direction,
time scope, metric applicability and supporting facts. A pass requires the
requested conclusions and material facts, no material contradiction, and valid
support from the supplied packet. A partially correct narrative is recorded as
partial for diagnosis but does not pass strict overall correctness.

For mixed questions, the numerical and interpretive results remain separate.
A correct quick-ratio calculation can coexist with an unsupported liquidity
judgment; a plausible judgment with wrong figures also fails overall correctness.
Do not credit a causal driver merely because the answer describes a correlated
change, or turn absence from a retrieved page into a claim that no litigation
exists. Check all requested years/entities, not merely a yes/no prefix or word
overlap with the reference. Literal reference wording is not required when a
semantically equivalent answer is fully supported.

### Citation/support and abstention axes

Structural citation validity requires the same report and an included zero-based
page ID, plus a literal supporting span present in the packed text under the
frozen whitespace-matching policy. Semantic support is a separate manual judgment
that the span actually entails the claim and supports the year/unit/association.
An otherwise correct answer without evidence support is not a supported answer.

Report task correctness and supported task correctness over all 24 questions.
An abstention scores zero on the answerable benchmark task, while a separate
context-availability judgment can mark it an appropriate abstention for the
provided packet. An attempted answer without required evidence can be an
unsupported guess even if its final value matches. Do not assume that missing
annotated pages alone determine context answerability: annotations may not list
all valid support and truncation can remove content from a retrieved gold page.

Blind outputs to condition labels, randomize review order with a fixed saved
seed, and have two reviewers independently assess unique completions with the
frozen rubric. Retain their separate decisions and adjudicate disagreements;
record reviewer availability if only one reviewer can complete the pilot. Reused
C/G outputs share one adjudicated judgment and must not inflate agreement counts.
No uncalibrated LLM judge is the sole correctness authority in this small pilot.

## 6. Annotated-page diagnostic after primary predictions are sealed

After all primary request/prediction hashes are saved, optionally spend the
predeclared **24-request** diagnostic allowance on native text from the annotated
evidence pages, ordered by ascending zero-based ID. Use the same generator,
schema and per-page/global budgets; all current questions have at most three
annotated pages. Never supply annotated snippets, reference answers or
justifications. Evidence labels may select pages only in this explicitly labeled
diagnostic; they remain excluded from primary prompts and retrieval inputs.

This helps separate page-selection failures from downstream extraction/reasoning.
It is not an unbiased retrieval condition, a guaranteed perfect context or a
mathematical accuracy ceiling: native text/annotations and the fixed prefix cap
can still omit useful content. Keep its results separate from the primary table;
do not use them to repair/retry primary answers or tune the prompt.

## 7. Reporting and stop criteria

Publish, by logical condition and with reuse disclosed:

- strict task correctness and supported correctness over all 24 questions;
- numerical final-result match, operand/units/sign/year/formula/arithmetic checks
  on the predeclared numerical subset, and interpretation pass on its own subset;
- citation validity and semantic support, answer/abstention coverage, schema/
  timeout/OOM/truncation counts and appropriate-versus-unsupported abstentions;
- paired N/OCR task gains/regressions and all five multi-page questions, including
  saved page recall and manually reviewed packed-context sufficiency;
- distinct requests versus aliases, exact prompt/response/output hashes, input/
  output tokens, model startup, per-request wall time and actual peak memory;
  charge only executed calls to cost and retain shared ingestion accounting;
- error categories: retrieval omission, packing loss, OCR/text/layout ambiguity,
  operand/sign/unit/year extraction, formula choice, arithmetic, interpretation,
  unsupported claim/citation, invalid output and reference ambiguity.

Do not call Recall@5 or complete evidence coverage an answer-accuracy estimate.
Do not infer generalization, statistical significance or energy savings from
these 24 dependent, previously inspected tasks. Public benchmark contamination
and pretrained financial knowledge are additional unresolved limitations.

End the bounded pilot after these requests and the adjudicated report. Any prompt,
model, quantization, packing, calculator, ledger or retrieval change requires a
separate versioned future study. Later company/document-held-out evaluation must
be excluded from this development process. Primary generation/evaluation implementation and real execution remain pending;
only feasibility setup and private evaluator preparation are implemented in the
separate continuation guide.
