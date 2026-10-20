# Completed synthetic v2: verified failures and implementation review

**Reviewed 2026-10-18; offline only.** The supplied
`synthetic-contract-v2-review(1).zip` has SHA-256
`bb64b96f9d581f30cb85ec1c496863cf659fa02becce6f4be163c342e5251e14`.
The machine-readable record is [SYNTHETIC_V2_RESULTS.json](SYNTHETIC_V2_RESULTS.json).
The next design is [proposed separately](ANSWER_CONTRACT_NEXT_DESIGN.md).

All six v2 requests completed. Resource collection and the intended FA-off runtime
reconcile. All six responses satisfy the actual schema and recorded grammar, but
**only `missing` passes strict mechanical validation (1/6)**. Source review also
agrees with that abstention. Overall answer-generation feasibility is **not
established**. This is fictional setup evidence, not FinanceBench accuracy.

Both six-request ledgers are exhausted: **12 attempted requests, zero remaining
authorized**. This review submitted zero requests. Neither campaign, its failures,
setup, ledger, environment, OCR cache nor expansion v1 / k=5 was changed. No
FinanceBench or annotated-page answer was generated. Historical v1/v2 execution
guides are not permission to repeat an exhausted campaign.

## 1. Artifact and preservation audit

The archive contains 58 files: the offline predecessor audit, four before and four
after snapshot files, and the separate v2 setup/ledger/predecessor audit plus 46 run
artifacts. Verification reconciles:

- the v2 setup SHA `d1a496141c9de242034e5114ded3bc5500fb44afe92986d96c13bd94e9cc4774`,
  six canonical request hashes and the campaign ledger;
- every SSE hash, reconstructed raw response, parsed object, backend-final record,
  input/output token count and saved validator diagnostic;
- identical v1/v2 prompt bytes and token IDs for all six cases, including five
  zero-based candidates and the 5120-token capacity input; no new answer prompt
  was substituted in v2;
- the original v1 run/setup/ledger bytes against the full lineage snapshot;
- all four before/after snapshot files byte for byte, including **110 matching
  hash entries** and three matching package inventories;
- 98 of those 110 actual files against the retained v1 artifacts and the Windows
  checkout reconstructed from the delivered patches. Twelve cache/model manifest
  bytes are absent from this bundle; their before/after hash entries agree;
- the recorded v2 source SHA
  `af3daf1cb3592b00a6788ed5eb796e469d4d3d1e9bae727bd5444787466a3f07`
  exactly against the delivered v2 code with the Windows path and mixed LF/CRLF
  bytes produced by the documented apply command.

The three inventories cover the supplied baseline `.venv`, CPU-OCR `.venv-ocr`
and answer `.venv-answer`; they are not full virtual-environment byte snapshots.
No GPU-OCR environment inventory is supplied in this archive. Individual cached
pages, model weights and backend binaries are not supplied either. Their recorded
identities/manifest hashes match; this review does not claim to rehash absent bytes.

The model, server, conversion identity, Python/package runtime, tokenizer inputs,
decoder, prompt, page IDs and source text match v1. The v2 effective runtime is
now explicitly Flash Attention **disabled**, Vulkan0 / RTX 3070 Ti, full 37/37
offload, context 6144, one sequence, batches 512/128 and F16 K/V. This resolves the
configuration discrepancy; it does not resolve the response failures.

## 2. Measured response failures

| Case | Visible result and source review | Why strict validation still fails |
|---|---|---|
| signed | Final -12.5 USD million and named identity calculation are correct. | The financial amount is typed `percent` with `currency=USD`, `scale=million`. This is a dimension contradiction, even though each field is individually in its enum. |
| scale | 1.25 × 1000 = 1250 is numerically correct; the bare final answer has no unit. | Both quantities are typed `percent`. The purported converted 1250 uses `scale=thousand`, not `million`: if treated as an amount, it is 1000 times too small. `scale_factor` is undefined and the expression uses literals instead of the declared IDs. |
| margin | Final margin 25%, prior margin 20%, and change +5 percentage points are correct. | Revenue/cost are incorrectly typed percent with USD/million. The cost span `Cedar Works FY2031: cost of sales 180 USD million.` is not a literal substring of the packet: the source has revenue between the prefix and cost. The formula substitutes numeric literals for named operands. |
| comparison | Operations is selected correctly; profit decline and increased input costs agree with the fictional report. | Financing is **+9**, despite source `(9)` meaning **-9**. The literal-only, unrequested cash-flow expression is unlinked to its defined IDs. `40 - (-12) - 9 = 43` is arithmetically correct as written, but financially inappropriate; signed net cash would be 19. It is not a subtraction-computation error. |
| missing | Canonical abstention identifies missing current liabilities. | No mechanical violation. Independent source inspection agrees; a single success is not evidence of a reliable general abstention detector. |
| capacity | Answer is `insufficient_evidence`, but status is `answered`, missing facts are empty, and a claim says the quick ratio **can be calculated**. | The claim contradicts “Current liabilities were not supplied.” The fixed expected-status check rejects it. Its literal citation is present but does not entail the claim. |

The missing-liabilities sentence survives the capacity prefix on all five pages.
Its unsupported positive claim is not explained by that fact being truncated out
of the packet. Context-length effects on model behavior remain unisolated.

Under the same v2 schema, formal schema validity rises from **1/6 in the saved v1
outputs to 6/6 in v2**. Strict mechanical/source compliance remains **1/6 to 1/6**.
This separates improved output form from financial correctness.

There is **no strict compliance gain** over v1 re-evaluated under v2: `missing`
alone passes both. Some representation errors disappear: value prefixes are gone,
comparison uses amount units and defined IDs, and percentage quantities use unit
scale. Other errors persist or change. Margin introduces the nonliteral cost
citation; scale now uses thousand for its converted figure; capacity switches to
the answered branch and drops its missing-facts list. These observations are not
controlled causal effects: grammar/validation and effective Flash Attention both
changed between campaigns. No output is repaired, replaced or promoted into a pass.

## 3. Schema and grammar: what is actually proved

Every backend-final record retains the same 12,383-byte GBNF grammar, SHA-256
`90f3a53882a22a0222155eb3854034a05ba356f7b02b49cd85c3d167a82d5561`.
Both the pinned **C++ converter** and companion **Python converter** reproduce it
byte for byte from the exact canonical wire schema. A standalone character-level
probe using the pinned C++ grammar implementation accepts all six original raw
responses. It rejects separate malformed-value, invalid-enum and invalid
abstention-array controls. No model, tokenizer vocabulary, sampler, server or GPU
backend was loaded for this probe; no inference was performed.

Thus there is **no demonstrated backend converter/enforcement defect for this
schema**. Enum membership, valid numeric strings and the represented array/branch
constraints are enforced. Grammar cannot establish financial signs, named-operand
references, source support or arithmetic by itself. Nor does a flat unit enum
couple that unit to its separately constrained currency and scale. V2's runtime
validator correctly rejects those wrong combinations; accepting their grammar
alone is not an answer-correctness pass.

The primary sources inspected locally are the clean llama.cpp b6500 commit
`a7a98e0fffed794396b3fbad4dcdbbc184963645`, especially
`common/json-schema-to-grammar.cpp`, `examples/json_schema_to_grammar.py`,
`src/llama-grammar.cpp` and `tests/test-gbnf-validator.cpp`. Their tested conversion
and recognition logic is unmodified. The host probe supplies only file I/O, UTF-8
iteration, string helpers and logging/assertion glue; it links no model runtime.
This checks the exercised schema and cases, not every JSON Schema feature.

## 4. Implementation defects and contract gaps

### D1. Answer/abstention consistency is one-way

In `src/finocr_answer/contract.py`, the answered branch accepts any nonempty answer
string, including the reserved `insufficient_evidence` marker. In `validation.py`,
the contradiction check runs only when status already says insufficient evidence.
The actual capacity object therefore passes the **generic** schema and response
mechanics. Its fixed synthetic expected-status check is what rejects it.

This is an implementation gap, not a reason to accept capacity. Future validation
must enforce the reserved-marker/status invariant in both directions, alongside
empty abstention claims/quantities, null calculation and explicit missing facts.
No generic invariant can replace manual review of the claim's meaning. The saved
v2 failure and 1/6 count remain unchanged.

### D2. Canonical JSON serialization changes operational schema order

The in-memory answered schema defines properties as:

`status → answer → claims → quantities → calculation → missing_information`

`canonical()` in `contract.py` uses `sort_keys=True`. `post()` in `feasibility.py`
serializes the entire request with it, sorting nested schema properties into:

`answer → calculation → claims → missing_information → quantities → status`

JSON object meaning is unchanged, but the pinned converter uses property order
to order generated fields. The recorded grammar follows the **wire** order;
status is last. Once capacity emits a nonempty claim, its prefix cannot match the
abstention alternative. The grammar then requires `answered` at the end. This
prefix commitment is reproduced offline; whether status-first generation would
improve the model's decision is **unmeasured**.

This is a serializer/interface and conformance-test defect, not a converter bug
or a mismatch to the sealed canonical schema hash. That hash ignores key order;
it cannot distinguish these operationally different grammars. Earlier compilation
success did not test the exact wire schema's behavior. A repair must separate
canonical identity hashing from deliberate wire ordering, test the actual request
bytes, and record the effective grammar hash. Merely reordering the source dict
while retaining `sort_keys=True` will not fix the transmitted order.

### D3. Prompt, schema and evaluator are not fully aligned

The v2 run intentionally kept the original instruction/prompt fixed. It describes
field names and unit choices, but does not state the complete strict abstention
shape, all required derived-quantity records, or the comparison case's strict
null-calculation rule. The schema and case-specific evaluator are stronger than
the model-facing contract in these respects. These rules should be stated and
versioned prospectively, without putting expected case answers/statuses or a
private rubric into the prompt/grammar.

For example, a separate handwritten control with a correct margin answer, named
formula and source operands fails when its duplicate derived-quantity records are
removed. The common schema does not require those records. This is a representation
alignment gap. It did **not** cause the measured margin failure: the actual output
does include all five records and independently fails dimensions/citation/linkage.

The single calculation object also cannot separately record and verify both the
margin formula and its percentage-point-change formula. That is a pre-primary
representation limitation, not a claim that the model computed the observed
change incorrectly. Any later multi-calculation contract needs its own prospective
version and explicit validation; it must not retroactively rescore these runs.

### Declared limits are not hidden model accuracy

Mechanics deliberately do not establish final prose meaning, quantity-role
association, formula meaning or citation entailment. An offline handwritten
counterexample with correct signed quantities but a positive final prose answer
passes mechanics. This demonstrates why mechanical pass must never be called
answer correctness; it is not a success of that counterexample. Semantic/manual
checks remain necessary. None of the five measured rejections is shown to be an
incorrect rejection of a wholly valid response.

### D4. Capacity's metaquestion and required status are ambiguous

The actual question asks **whether** the quick ratio can be calculated, rather
than asking for the ratio itself. A supported “No, current liabilities were not
supplied” can answer that metaquestion, while `functional_checks` hardcodes
insufficient evidence. A separate handwritten, source-supported negative-answer
control passes the generic contract and fails only `expected_status`. The harness
therefore conflates answering availability with producing the missing calculation.

This is a test-framing/status-policy gap. It does not validate the measured
response, which asserts that the ratio **can** be calculated and contradicts its
own abstention marker. Its failure and the 1/6 result remain. A future capacity
check should prospectively ask for the calculation and explicitly state the
common abstention policy, retaining the long five-page packet and budgets. Do not
rewrite this run's question or loosen its validator after seeing the response.

## 5. Verified resource/timing observations

| Observation | v2, FA disabled |
|---|---:|
| Completed requests / collected samples | 6 / 119 |
| Input tokens, case order above | 340, 333, 364, 356, 343, 5120 |
| Output tokens, same order | 252, 383, 796, 522, 63, 106 |
| Total generated tokens | 2,122 |
| Recorded startup wall | 1.697888 s |
| Sum of recorded request walls | 30.020446 s |
| Recorded run wall | 32.599924 s |
| Sampled whole-device peak used VRAM | 4,094 MiB |
| Sampled server peak RSS | 3,029,127,168 bytes (2.821095 GiB) |
| Sampled client peak RSS | 324,395,008 bytes (0.302116 GiB) |
| Maximum sampled sum of server/client RSS | 3,352,899,584 bytes (3.122631 GiB) |
| Minimum sampled whole-system available RAM | 5,726,253,056 bytes (5.332989 GiB) |

All requests are below the 1024-output cap and 180-second request deadline, with
no recorded truncation, transport/deadline failure or resource sampling error.
VRAM is whole-device usage including display/other processes, sampled at one
second: it is a lower bound on peak. RSS sums can double-count shared pages.
Windows peak working set is summary-only and not independently recomputable from
the supplied sample fields. There is no repeated timing study, energy measurement,
isolated process VRAM estimate or causal FA performance comparison.

## 6. Completed review validation and stop point

The unchanged v2 implementation's **219-test suite passes** on the development
host. Fourteen additional offline characterization probes pass: they reproduce
the original scores, exact C++ wire grammar, prefix commitment, invalid-control
rejections and the documented gaps. Passing these probes means the current defects
are reproduced, **not repaired**. Future repair regressions must require the
counterexamples to fail; they must not make these false acceptances the policy.
No generation runtime/test suite was changed by this documentation continuation.

The researcher separately reported a complete Windows 219-test pass; this archive
does not include that full test log. Actual model outputs, logs and resource
samples reviewed here do come from the completed Windows v2 execution.

Proceed only with the [zero-inference contract gate and separately proposed
qualification design](ANSWER_CONTRACT_NEXT_DESIGN.md). The present allowance stays
exhausted. All original failures remain controls; no retry, reset, model switch,
prompt sweep, new OCR/retrieval tuning or FinanceBench generation is authorized.
The private scoring rubric's three pre-generation adjudication holds also remain.
