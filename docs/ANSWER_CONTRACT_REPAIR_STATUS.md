# Offline contract repairs: implemented, inference paused

**Offline implementation validated 2026-10-19 UTC.** Apply this increment over preparation + validation-v2 + the applied
`synthetic-v2-review-docs.patch` (SHA
`edb59910af3c28c718dd4b3de4f0b58b264b9339770dba53b2d1bb3d50008800`).
It does not apply directly to bare `828ba06`. Read the
[staged Windows guide](ANSWER_CONTRACT_REPAIR_WINDOWS.md).

## Completed implementation

The current contract is `typed-response-v3-offline`; fictional cases have a
separate `fictional-cases-v3-offline` identity. Neither is an inference setup seal.

- Ordered `wire()` serialization preserves status first in the complete nested
  schema envelope; canonical JSON remains a separate identity-hashing function.
  Both HTTP helper paths and saved-request serialization use the ordered bytes.
- Tagged quantity alternatives couple amount/USD/amount-scale and dimensionless
  percent/percentage_points/ratio with none/unit. The discriminator is unit first.
  Independent runtime dimensional checks remain.
- Answered responses reject the reserved abstention marker, including surrounding
  whitespace/case variants, without rewriting the response. Abstention still
  requires the exact canonical marker, no asserted claims/quantities/calculation,
  and nonblank missing facts.
- The common prompt states source operands, requested and derived result records,
  literal citations, named expressions, conversion constants, the one-calculation
  limitation and null calculation for selection/narrative questions. A calculation
  result must also have a matching typed quantity. All requested margin components
  remain required; arithmetic/sign/year/scale/source-link checks are retained.
- Capacity prospectively requests the quick ratio itself. Its source pages and
  five-page/800-token-prefix budgets are unchanged; the original availability
  question remains in the frozen historical cases. The other five questions match.
- `historical_contract_v2.py`, `historical_validation_v2.py` and explicit historical
  case/packing helpers preserve the old schema, prompt and diagnostic behavior.
  Historical auditing uses those definitions. Exact v2 raw-output fixtures and
  saved diagnostics are retained separately; original reports are not rewritten.
- `run()`, follow-up preparation and setup sealing stop immediately with an
  unconditional pause guard. There is no environment override, enable flag, new
  ticket, allowance or inference command in this continuation. Legacy lifecycle
  tests mock both the guard and every backend/transport; real guard tests do not.

Wrong numeric strings, dimensions, scale/year/sign, undefined/unused IDs, literal
substitution, arithmetic, missing numerical components and invalid citations stay
failures. Literal presence is not semantic support: the API leaves semantic and
formula review pending and never labels a mechanically valid response fully
supported. The actual capacity contradiction remains rejected. General entailment
and final prose correctness still require source/manual evaluation; no keyword
heuristic or LLM judge has been added.

## Completed offline validation

| Check | Development-host observation |
|---|---|
| Complete suite | **250 tests pass**, including 31 new repair tests |
| Revised fixture gate | Six handwritten positive fixtures and 17 targeted negative fixtures behave as required; none is a model output |
| Grammar conversion | Pinned b6500 Python and C++ converters produce the same ordered 18,525-byte GBNF |
| Character recognition | Portable standard-library recognizer and pinned C++ recognizer agree on all 23 fixtures |
| Historical compatibility | Exact v2 raw bytes and diagnostics reproduce; every genuine failed output from both campaigns remains rejected |
| Historical tokenizer parity | All six original prompt bytes/token IDs reproduce before revised packing is checked |
| Revised input token counts | signed 620, scale 613, margin 644, comparison 636, missing 623, capacity 5120 |
| Capacity limits | 4096 evidence + 1024 overhead; five source-body prefixes of 800 tokens each |
| New inference / authorization | **0 / 0** |

The host used the existing tokenizer dependencies and pinned vocabulary/merges,
with byte identities verified and historical token parity established. No weights
were read or model/backend/server initialized. Windows will use the existing full
local tokenizer bundle; its checks remain pending local execution. UTF-8 file/stdout
handling and LF grammar normalization are explicit for the pinned converter on
Windows. No environment or dependency installation is required.

Grammar SHA-256:
`dd3d90c3e13de2e852727aa6f49776edd6b6699b21d62ebdee65d5b69df60fce`.
The offline manifest separately records canonical schema identity, ordered schema
bytes, effective grammar, instruction, case and code identities. It is not a model
run manifest, budget ticket or source-correctness score.

## Historical results and outstanding work

V1 and v2 each spent six real requests: **12 spent, zero remaining authorized**.
The verified v2 result is still six grammar/schema-valid outputs and **1/6 strict
mechanical passes**, not 250 tests or six handwritten examples as model accuracy.
Neither old run, ledger, raw failure, setup nor measured result has been rescored.
`SYNTHETIC_V2_REVIEW.md` and `SYNTHETIC_V2_RESULTS.json` remain byte-identical.

Existing baseline/OCR environments, caches, report/page IDs and all `src/finocr`
Python bytes remain unchanged, including frozen expansion v1 at k=5. New code
stays in its sibling answer package. README is omitted from the increment to
preserve local results updates. Original recovery and earlier patch files remain.

Pending: actual Windows execution of this new offline guide and review of its
preservation snapshots. Any future model qualification still needs its own
explicit prospective authorization and implementation; no such allowance exists
here. Primary FinanceBench generation and annotated-page diagnostics remain
unimplemented/paused. The private rubric's three pre-generation adjudication
holds remain. A passing offline gate does not authorize generation.
