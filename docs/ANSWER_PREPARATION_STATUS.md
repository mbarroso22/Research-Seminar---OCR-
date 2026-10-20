# Answer preparation status

**Latest continuation: offline repairs implemented; inference remains paused.**
Read [the repair status](ANSWER_CONTRACT_REPAIR_STATUS.md) and
[zero-inference Windows commands](ANSWER_CONTRACT_REPAIR_WINDOWS.md). The revised
contract has 250 passing tests and no model outputs, setup seal or new allowance.
Historical v1/v2 results below remain unchanged; 12 requests are spent, zero remain.

Continuation base: `828ba06`, `native-ocr-pilot-results`. The verified native / CPU
/ GPU OCR pilot is unchanged. Expansion v1 at k=5 remains frozen.

The original implementation supplies isolated setup, six built-in fictional
feasibility checks and evaluator preparation. Its completed run is now documented
in [the independently verified synthetic review](SYNTHETIC_FEASIBILITY_REVIEW.md).
The incremental strict-validation continuation has its own
[staged Windows guide](ANSWER_VALIDATION_V2_WINDOWS.md). It does not implement
primary FinanceBench or annotated-page generation.

The candidate is official Qwen3-4B-Instruct-2507 at an immutable revision, locally
converted to Q4_K_M using pinned llama.cpp b6500. Standalone Windows Vulkan avoids
changing Paddle/CUDA environments or the driver. Both supplied Windows campaigns
completed six fictional requests on driver 537.70. V1 auto-enabled Flash Attention;
the completed v2 logs now verify disabled FA and the frozen runtime. Resource
checks pass, but strict output compliance remains **1/6**. These are setup
observations, not benchmark accuracy or successful overall feasibility. Read
[the verified v2 review](SYNTHETIC_V2_REVIEW.md) and its JSON record.

The v1 read-only audit reconciles all original request/response hashes, the exhausted
six-request ledger and 121 resource samples. Strict offline mechanical validation
passes only the missing-evidence response (1/6); capacity's contradictory claim
now also fails. Invalid unit/scale strings, malformed values, unlinked/undefined
calculation operands and the financing sign remain failures. Literal citations
and correct final numbers alone do not establish supported correctness.

The incremental implementation pins typed JSON alternatives, named Decimal
calculation checks and fail-closed runtime verification, including explicit
`--flash-attn off`. The completed v2 run reproduced all six original prompts/token
IDs and retained a separate seal/cache/ledger. The cumulative **12-request allowance
is exhausted; zero additional requests are currently authorized**. Do not repeat
the historical command or recreate a campaign. Both runs and all failures remain.

Offline review exactly reproduces v2 diagnostics, resource summaries, preservation
snapshots and the recorded source fingerprint. All six raw responses satisfy the
wire grammar; the pinned C++ and Python converters reproduce it byte for byte.
Four implementation gaps are documented: asymmetric answer/abstention validation,
recursive key sorting that puts status last, incomplete prompt/evaluator alignment,
and capacity's availability-question/status-policy ambiguity. Actual errors in
unit/scale, sign, operand linkage, citation and unsupported claim remain failures.
No generation code or old validation outcome is changed by this documentation.

All 219 existing tests and 14 offline characterization probes pass on the
development host; the probes demonstrate gaps rather than certify a repair. The
researcher separately reported a complete Windows 219-test pass. The proposed
zero-inference contract gate is now [implemented separately](ANSWER_CONTRACT_REPAIR_STATUS.md).
Its 31 additional repair tests are distinct from those earlier review probes.
Any model qualification remains unimplemented/paused and has no new allowance.

A separate evaluator-private bundle contains all 24 source-reviewed rubric items.
Original task bytes, answers and evidence labels remain unchanged. All six source
PDFs match cohort SHA-256/page counts; all 25 annotated pages plus one tax-note page
were visually reviewed. Three source/reference ambiguities remain explicit holds.
Researcher adjudication/final freeze is pending before any benchmark answers. The
private key and issue details are deliberately absent from this public patch and
from the generator's accepted inputs.

Mechanical evaluator checks cover signs, fiscal years, currency, equivalent scales,
per-quantity Decimal display rounding, restricted arithmetic and literal zero-based
citations. They do not establish interpretation or semantic support. Later blinded
human scoring and all measured answer results remain pending. Source adjudication
must precede predictions, preserve references, and version any scoring overlay.

The original bounded protocol remains the design authority. Backend setup is now
concrete, but primary request deduplication, benchmark packing, ranking/cache
validation and blinded evaluation execution are still future implementation.
Synthetic packing exercises the fixed budgets and prefix policy without consuming
FinanceBench questions or answers. Its source-only tests are not pilot results.

New runtime code lives in the sibling `finocr_answer` package. Every existing
`src/finocr` Python byte and its source-fingerprint membership stay unchanged,
preserving the OCR resume code contract as well as the completed caches.
