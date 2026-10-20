# Proposed next bounded design: contract conformance before inference

**Design dated 2026-10-18. Offline part A is now implemented; inference part B
remains a proposal, unimplemented and unauthorized.** See
[the repair status](ANSWER_CONTRACT_REPAIR_STATUS.md) and
[offline-only Windows guide](ANSWER_CONTRACT_REPAIR_WINDOWS.md).
The [completed v2 review](SYNTHETIC_V2_REVIEW.md) verifies 1/6 strict mechanical
compliance despite successful resource/runtime checks. The cumulative **12-request
budget is exhausted**. There are **zero currently authorized additional requests**.
This document supplies no inference command and does not alter a ledger or budget.

## Decision

Treat the next step as a contract/interface repair, not another model, OCR or
retrieval sweep. Complete an offline conformance gate first. Only after a concrete
repair and its tests are reviewed should one separately authorized, prospective
six-request synthetic qualification be considered. Keep the saved v2 campaign as
the measured FA-off development control. No rerun of that control is needed.

This recommendation does not claim a new prompt or stronger grammar will fix
signs, financial interpretation or abstention. The preserved cases are already
inspected development checks, so later success cannot establish generalization.

## A. Proposed offline repair and conformance gate — zero requests

These requirements now define the offline repair implementation. Its checks do
not execute a campaign or authorize part B:

1. **Align one versioned model-facing contract.** Explicitly describe typed amounts,
   percentages, percentage-point changes and ratios; separate currency and scale;
   define named source operands versus numeric conversion constants; require all
   requested numerical components and concise source support. State the canonical
   abstention shape and when calculation is null. Do not include any of the six
   expected answers, case-specific expected statuses, reference values, FinanceBench
   labels or private scoring key in prompts or grammar.
2. **Preserve intentional discriminator order on the actual wire.** Use a dedicated
   ordered request serializer while retaining a separate canonical hash function.
   Generate status before answer/claims in every top-level branch. A source-dict
   reorder alone is insufficient while the old recursive `sort_keys=True` remains.
   Record exact wire-schema bytes and the compiled effective grammar hash, not only
   an order-insensitive schema digest. Test the full transmitted representation.
3. **Encode compatible quantity shapes.** A source-independent tagged union should
   couple amount with the permitted currency and amount scales, and percent /
   percentage_points / ratio with currency none and scale unit. Keep the same
   dimensional runtime rejection as an independent check. Grammar cannot enforce
   financial sign, source meaning or that an operand is the right business metric.
4. **Make answer/abstention invariants bidirectional.** `answered` must reject the
   reserved abstention answer marker; insufficient evidence must retain its strict
   empty-assertion shape and explicit missing facts. Continue source/manual review
   for contradictory prose in any field. Do not replace the test with keyword
   acceptance or remove the source-specific capacity rejection.
5. **Freeze evaluator representation requirements.** Say exactly where derived
   numbers and calculation results must appear. Keep the existing required signs,
   values, years, dimensions, completeness, source linkage, arithmetic and citation
   requirements. Do not resolve a representation gap by deleting a required
   correctness facet. The minimal qualification can retain the one-calculation
   shape if its limitation and manual review of the percentage-point derivation
   are explicit. A calculations-array redesign is a separate scope/version
   decision before benchmark work, not an unnoticed change to the old evaluator.
   Clarify the fictional capacity **question** prospectively: request the quick
   ratio, with the same general missing-facts abstention policy, instead of asking
   the answerable metaquestion “Can it be calculated?”. Preserve its original
   wording and failure in both saved controls; this is an explicit future task
   wording change, not a retrospective status exemption.
6. **Require positive and adversarial offline fixtures.** Test handwritten valid
   responses and targeted one-defect mutations: wrong unit tuple, wrong scale/year,
   malformed number, sign reversal, undefined/unused ID, literal-only formula,
   wrong arithmetic, nonliteral/irrelevant citation, and both directions of
   abstention conflict. Preserve the six original raw outputs from each campaign
   and their historical failures unchanged. Record diagnostic-only fixture
   mutations separately; never treat a repaired fixture as a model output.
7. **Verify the pinned converter against the exact wire schema.** Check actual GBNF
   acceptance/rejection, not compilation success alone. Compare property-order
   and discriminator-prefix controls. Both the standalone C++ character recognizer
   and companion Python conversion need no weights, server or inference. Unknown
   schema features/warnings, grammar drift or unexpected acceptance stop the gate.

All old invalid outputs must remain failures under their original validators and
recorded protocols. A new version must retain at least the same correctness
requirements; no field coercion, unit rewriting, dropping extra claims, relaxed
tolerance, repaired citations or literal-formula exemption is allowed.

Maintain a clear distinction between typed schema validity, generic mechanics,
source-specific checks and manual semantic review. Verify each independently.
The existing 219 passing tests did not cover these interface gaps; add meaningful
negative regression expectations for the repair instead of relying on that count.

## B. Proposed qualification, only if later explicitly budgeted

| Item | Proposed fixed limit / condition |
|---|---|
| Additional requests | **At most 6**, one completion per preserved fictional case |
| Cumulative synthetic ceiling | **18 only if separately authorized**; current authorized ceiling remains 12 |
| Campaigns / retries | One new campaign; zero retries, repairs or best-of-N selection |
| Model/backend/device | Same recorded Qwen3-4B-Instruct-2507 revision, local Q4_K_M bytes, llama.cpp b6500 server bytes, Vulkan0/RTX 3070 Ti |
| Runtime/settings | Same existing `.venv-answer`, package inventory, verified FA off, full offload, F16 K/V, context 6144, parallel 1, batches 512/128, threads 6 |
| Decoder/output | Same greedy seed-0 decoder, one completion, at most 1024 output tokens, 180-second request deadline |
| Sources/packing | Same five other fictional questions; prospectively clarified capacity calculation question; same five zero-based source pages, 800 body tokens/page, 4096 evidence tokens and 5120 total input ceiling |
| Intended changes | One prospectively frozen repaired contract, aligned instruction, clarified capacity question, ordered wire schema and corresponding validator/grammar identity |
| Benchmark/OCR/retrieval requests | **0**; expansion v1 / k=5 and every ranking/cache stay frozen |

This is a **bundled interface-repair qualification**, not a single-factor causal
ablation of prompt wording versus schema order versus dimensional grammar. Its
purpose is to determine whether one internally consistent interface can satisfy
the predeclared synthetic requirements with this model/backend. Keep v2 as the
saved control and report all changes. Do not attribute a difference to one repair
or compare latency as an isolated hardware/FA effect.
The clarified capacity wording is also a task change: report it separately from
the five unchanged questions rather than treating it as an exactly matched pair.

Before any future completion, verify the exact model/runtime/source/grammar and
new prompt/token identities, all six token budgets, FA-off runtime and input
allowlists. A larger aligned instruction may change non-capacity token counts;
capacity must still be prepared at the exact 5120-token boundary. Its unchanged
source body prefixes and page coverage must be checked locally before allocating
requests; this document does not claim the unimplemented prompt already fits.

Use a distinct new directory, setup seal, cache and campaign ledger linked to
both exhausted campaigns. An existing directory/ledger must prevent restarting.
Charge attempts before submission, including failed transports. Save raw SSE,
exact content, parsed/invalid objects, diagnostics, timing and samples on every
outcome. Stop on runtime/identity/capacity mismatch before generation, or on a
transport/deadline failure after retaining the partial campaign. Unspent requests
do not authorize a second campaign or retries.

The qualification criterion is all six strict mechanical/source checks **and**
source/manual review of final figures, signs, formulas, literal/semantic support,
interpretation and abstention. Record any reviewer disagreement; do not convert
a correct final number with wrong operands into supported correctness. Sampled
resource collection and deadlines must also pass. Even 6/6 is setup evidence only.

After those at most six attempts, stop and document every failure. No automatic
prompt adjustment, new model, quantization change, grammar sweep or fresh ticket
is included. If the repaired interface still fails, review the failure categories
and revise the research design before proposing any further inference.

## C. FinanceBench remains a separate decision

The 24-question generation stage is not implemented or authorized here. Neither
the proposed 48 distinct primary requests nor 24 annotated-page diagnostics may
be borrowed to fund synthetic retries. Resolve the three private source/reference
holds and freeze the source-checked rubric prospectively before benchmark answers.
Numerical correctness, financial interpretation and source support remain separate
evaluation axes. Existing native/OCR page coverage and retrieval results are not
answer-accuracy estimates.

No existing environment, OCR cache, report/page ID, raw reference label, retrieval
query, tokenization, score or ranking may change as part of this proposal. Any
later generator condition must use the frozen expansion-v1 k=5 packets and retain
the earlier numerical/interpretation reporting plan and company/document holdout
boundaries. Do not promote a repaired, already inspected synthetic case into a
held-out result.
