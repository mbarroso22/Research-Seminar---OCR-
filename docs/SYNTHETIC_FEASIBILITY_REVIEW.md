# Verified synthetic feasibility review and validation repair

**Reviewed 2026-10-18.** This reviews `synthetic-review-20261018T220936Z.zip`
(the supplied copy has `(1)` in its filename). It is setup evidence, not FinanceBench
answer accuracy. No new model inference was executed while reviewing or testing.
The incremental patch applies over `answer-feasibility-preparation.patch`
(SHA-256 `3a49514a0e0af185c829e07be58750773c9127b1394da396bb27c9a86e32bd1f`)
on base `828ba06`, not directly to the bare commit.

Read [the staged follow-up Windows guide](ANSWER_VALIDATION_V2_WINDOWS.md). The
old run, setup, raw failures and exhausted campaign ledger remain authoritative
historical artifacts. The patch does not rewrite them or change existing packages,
model/backend bytes, OCR caches, original task labels or expansion v1 / k=5.

## 1. Artifact verification

The supplied archive SHA-256 is
`7308ac38e54bdba41954d216af47a562638e10b3ee326ad661c46a8f972b8a2c`.
All 48 supplied files were read without modification: 46 run artifacts plus the
setup manifest and campaign ledger. Independent checks reconcile:

- six case IDs and charged requests, setup SHA, canonical request hashes and ledger;
- prompt bytes, saved token IDs/counts, original decoder/schema, five source page
  prefixes and the maximum input/evidence budgets;
- raw SSE hashes, reconstructed content, parsed JSON, terminal responses and token
  counts; all six completed without reported truncation/deadline failure;
- 121 resource samples with saved RSS, available/used RAM and device-wide VRAM
  summaries; no recorded sampling errors;
- the original implementation source fingerprint against the delivered v1 files
  with Windows paths and CRLF bytes. Recorded source SHA is
  `0896670ddec9f6f294282e0352969a254498b8d5feab9cf1721a03ea9657ca1e`.

The recorded setup SHA is
`97833de25a4195a3cb4ccea60a6c8402a517b383d990b2cde0570458176a9a60`.
The local Q4_K_M file is recorded as 2,497,278,880 bytes, SHA
`80f7dccce5ae984d2b40ba998871288e367fcb76a759f89c55e7139e4632f0e1`;
backend server SHA is
`62e6a5fec588ff3ea6d26a507db4373e56c850db19b39239bd30f5e7d87751cd`.
Those binaries/weights and conversion/acquisition files are not in this review
bundle. Their recorded identities are checked for lineage here; the follow-up
preparation rehashes their actual bytes on the Windows machine.

## 2. Saved output review

| Case | Correct visible content | Failure retained / newly exposed |
|---|---|---|
| signed | Final answer states -12.5 USD million; A is a defined operand | Quantity `unit="USD million"` violates the instructed `unit="amount"`, separate currency/scale contract. No unit rewriting is allowed. |
| scale | 1.25 × 1000 gives 1250 numerically | `value="value: 1.25"` is malformed; units `billion USD` / `million USD` are invalid quantity-unit values. `scale_factor` is undefined; the literal-only expression does not use declared quantity IDs. |
| margin | Final gross margin 25% and increase 5 percentage points are numerically right | Amount units `million` and scales `percent` / `percentage_points` are invalid. The calculation is all numeric literals despite declared revenue/cost IDs, so the apparent arithmetic pass does not establish operand provenance. |
| comparison | Operations selected correctly; profit decline and input-cost explanation agree with the fictional text | All values carry invalid `value:` prefixes and units `million USD`. Financing is presented as positive 9 despite source `(9)`. Calculation IDs `operations`, `investing`, `financing` are undefined because quantities use `_cash` IDs. Expression `40 - (-12) - 9 = 43` is arithmetically correct as written, but is an unrequested, financially inappropriate total; correct signed net cash would be 19. |
| missing | Coherent abstention identifying absent current liabilities | No mechanical violation found; the saved response also agrees with the source on manual inspection. This does not validate a general abstention detector. |
| capacity | Status and answer label abstain; missing facts are identified | Claim says the quick ratio **can be calculated**, citing “Current liabilities were not supplied.” Literal span validity is true but semantic support is false; the answer contradicts its own abstention. |

The old automated checks already rejected the first four cases. They incorrectly
left the capacity case looking mechanically acceptable while deferring semantic
review. Under the new strict response contract, five saved outputs fail and only
`missing` passes mechanical checks. **This 1-of-6 compliance count is not answer
accuracy.** Several visible final answers are correct while their structured
quantities/calculations are invalid. Nothing is repaired or rescored into a pass.

## 3. Flash Attention discrepancy

The recorded command omitted `--flash-attn`. The server log explicitly says:

```text
llama_context: flash_attn    = auto
llama_context: Flash Attention was auto, set to enabled
```

Thus the actual run used Flash Attention, despite the guide's intended disabled
configuration. The wrapper relied on an inaccurate/default description rather
than explicitly setting and checking it. Disabling Vulkan cooperative matrices
is a different setting and does not disable Flash Attention.

The pinned b6500 source supports `--flash-attn off`:
[argument parser](https://github.com/ggml-org/llama.cpp/blob/a7a98e0fffed794396b3fbad4dcdbbc184963645/common/arg.cpp),
[context auto-selection](https://github.com/ggml-org/llama.cpp/blob/a7a98e0fffed794396b3fbad4dcdbbc184963645/src/llama-context.cpp),
[enum/log names](https://github.com/ggml-org/llama.cpp/blob/a7a98e0fffed794396b3fbad4dcdbbc184963645/src/llama.cpp).
The repaired runner explicitly requests off and requires runtime `flash_attn =
disabled`, full 37/37 offload on Vulkan0/RTX 3070 Ti, context 6144, one sequence,
batch/microbatch 512/128 and F16 K/V. Missing, auto-enabled or mismatching settings
stop the owned server **before the first completion request**. Original logs are
preserved; the historical run is not relabeled as an FA-off reproduction.

## 4. Verified setup resource observations

| Recorded / recomputed quantity | Observation |
|---|---:|
| Completed requests | 6; original ledger exhausted |
| Input tokens in case order | 340, 333, 364, 356, 343, 5120 |
| Generated tokens in case order | 253, 384, 804, 536, 63, 136 |
| Total generated tokens | 2,176; every response below the 1,024 cap |
| Recorded startup wall | 1.791403 s |
| Sum of recorded request walls | 30.257434 s |
| Recorded run wall | 32.882934 s |
| Device-wide sampled peak used VRAM | 4,017 MiB |
| Server sampled peak RSS | 3,052,982,272 bytes (2.843311 GiB) |
| Client sampled peak RSS | 322,449,408 bytes (0.300304 GiB) |
| Sampled maximum sum of server/client RSS | 3,366,297,600 bytes (3.135109 GiB) |
| Minimum sampled system available RAM | 6,666,489,856 bytes (6.208652 GiB) |

These are observations of the **FA-enabled synthetic run**. GPU samples include
display/other processes and are a lower bound on peak, not isolated process VRAM.
RSS sums can double-count shared pages. Windows server peak working set is in the
summary only and cannot be independently recomputed from supplied sample fields.
Run wall is not conversion/download time or a repeated performance benchmark.
Successful allocation and six completed requests do not establish the intended
FA-off condition, semantic correctness, energy savings or FinanceBench feasibility.
Baseline before/after package inventories are absent from this archive; the new
guide supplies preservation checks rather than claiming those were reviewed here.

## 5. Implemented validation changes

- Typed JSON grammar constrains quantity units, USD/none currency, scales, fiscal
  years, identifiers and signed decimal strings. Grouped numbers, parentheses and
  Unicode minus remain valid financial formats; `value:` prefixes, dollar signs
  in a numeric field, malformed grouping, exponents and nonfinite values fail.
  Unknown units are rejected rather than mapped into acceptable ones.
- Runtime validation checks every quantity, including extras; dimensionless values
  require scale `unit` and currency `none`. Source year/sign/scale checks stay
  separate. All requested synthetic numerical components remain explicit.
- IDs must be unique; every calculation operand must be defined; declared IDs must
  match expression names. Literal-only substitutions, unused/unknown operands,
  unsafe arithmetic, wrong recomputed results and incorrect requested result units
  fail. Numerical arithmetic and financial formula meaning remain distinct.
- A strict abstention uses the canonical answer `insufficient_evidence`, empty
  claims/quantities, null calculation and nonempty missing facts. This prevents a
  simultaneous asserted solution. General semantic entailment/formula review is
  still manual; valid literal spans never establish it automatically.
- Strict JSON parsing rejects duplicate keys/nonfinite constants. Raw bytes and
  parsed-but-invalid responses remain saved; no retry, repair prompt or alternate
  successful completion is selected.
- Status now distinguishes `validation_failed` from mechanically valid responses
  awaiting manual review. Pending review strings are never counted as true checks.

The original instruction text, questions, source text, packer, ranking/page budget,
model/backend/quantization, tokenizer, decoder, context and timeout are fixed.
The optional follow-up changes the output grammar/validator and makes the intended
FA-off condition explicit. It is a setup repair involving two changes, not a
causal ablation that can attribute output or latency differences to one factor.
All six prompts/token IDs must match the historical controls before any inference.

## 6. Explicit additional budget and stop point

Offline audit and setup preparation spend **zero** inference requests. One optional
new campaign `synthetic-contract-v2` may spend at most **six additional requests**,
one completion per same fictional case, maximum 1,024 output tokens and 180 seconds
each. Including the exhausted v1 campaign, the cumulative synthetic ceiling is
**12 requests**. No primary FinanceBench or annotated-page request is allowed.

This is an explicit setup-budget amendment to the original six-request allowance.
The proposed later 48 distinct primary and 24 diagnostic ceilings are unchanged;
if later separately authorized, the overall design ceiling becomes 84 rather than
78. This patch runs none of those benchmark requests and does not implement them.

The new ticket, seal, cache, ledger and run live under the fixed sibling directory
`followups\synthetic-contract-v2`; original v1 files remain untouched. Copied setup
paths, changed limits and alternate run roots are rejected. The ticket cannot be
prepared twice; the runner cannot restart an existing campaign, even after a
partial run. Attempts are charged before submission. At a transport/deadline error,
stop and retain the partial output and spent budget. Do not delete a ledger or
rename a campaign to reset the limit. No unbudgeted automatic retries are included.

After those six requests, stop for source/manual semantic review even if exit code
is 0. Further inference needs another explicit versioned protocol/budget. The
private FinanceBench rubric's three pre-generation adjudication holds remain
unchanged; no primary answers, retrieval tuning or new OCR are authorized.
