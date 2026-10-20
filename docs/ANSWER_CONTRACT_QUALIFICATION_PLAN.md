# Repaired-contract synthetic qualification: prospective plan

Prepared 2026-10-19. **Plan only; execution is not authorized.** Currently spent:
12 synthetic requests. Currently remaining: **0**. No budget, ticket, setup seal,
campaign ledger, inference command, model output or FinanceBench answer is created
by this document. The existing unconditional inference pause stays in place.

## Evidence independently reviewed

Source: the supplied `offline-contract-repair-review(1).zip` (the attached Windows
review export). Archive SHA-256:
`f7e5d2dba70867f45eae7996c803e844ffc78daa20a73f9d773116c6e9cb4449`.
The archive passes ZIP integrity checks.

| Evidence | Independently checked finding |
|---|---|
| Repair-test log | 31 distinct test records finish `ok`; `Ran 31 tests in 2.273s`, final `OK`, no skips |
| Complete-test log | 250 distinct test records finish `ok`; `Ran 250 tests in 60.236s`, final `OK`, no skips; the 31 repair tests are included, not additional |
| Grammar-only gate | `grammar_and_fixture_checks_pass_tokenizer_pending`, correctly distinguished from the complete gate |
| Grammar plus tokenizer gate | `offline_checks_pass`; all six historical prompt/token controls reproduced according to the report |
| Fixture verification | Independently recomputed all 23 fixture results against the attached grammar and current validator: six handwritten positives pass; all 17 one-defect negatives fail mechanics; reported diagnostics match |
| Schema/instruction/cases | Wire schema, envelope, canonical schema, instruction and case identities match the repaired implementation; Windows instruction-file CRLF is normalized only to compare its logical UTF-8 instruction identity |
| Tokenizer cross-check | All six prompt hashes, token-ID hashes, body lengths, page IDs and token counts match the earlier independent host tokenizer check exactly |
| Source identity | The reported Windows fingerprint reproduces from all 24 fingerprinted files in the tested CRLF checkout, using Windows relative-path separators and actual mixed line endings |
| Preservation | All four before/after snapshot files are byte-identical: 161 protected-file hash records plus three package inventories |
| Historical preservation | Rehashed 96 historical run/setup/ledger files against the earlier raw archives; every available comparison matches the snapshots |
| Historical v2 | Still 1/6 mechanically passing, only `missing`; the two preserved campaign ledgers each record six attempts: 12 spent, 0 currently remaining |
| New inference | Both offline reports record zero inference and zero authorization; the inspected current public run, follow-up and seal entry points retain their unconditional pause |

The test logs contain expected mock-run `validation_failed` messages and a corrupt
PDF fixture warning. Their surrounding tests finish `ok`; these messages are not
new model completions. The Windows tests were verified from their logs, not
rerun remotely in this review. Package inventories do not prove every environment
binary unchanged. Cache-manifest snapshots do not hash every OCR-cache file or
attest another machine. The supplied evidence supports the reported offline-only
activity; it is not filesystem-wide or network-wide monitoring.

These are completed **contract-development checks**. They establish neither new
model correctness nor generalization. Historical raw outputs and the historical
1/6 result must never be relabeled as repaired-contract outputs.

## Proposed scope and accounting

This is one bundled interface-repair qualification on the six already inspected
fictional development cases. It is not a prompt/schema causal ablation, held-out
test or FinanceBench accuracy experiment. Keep the saved FA-off v2 campaign as
the historical comparison; do not rerun either old campaign.

| Item | Proposed rule, contingent on later explicit authorization |
|---|---|
| Additional completion attempts | At most six, one per case, one completion each |
| Campaigns | One new campaign; no restarts, second campaign, resume after interruption or replacement directory |
| Fixed order | `signed`, `scale`, `margin`, `comparison`, `missing`, `capacity` |
| Retries and selection | Zero retries, repair prompts, regeneration, best-of-N, fallback models or answer selection |
| Accounting | Charge and durably record an attempt before submitting any completion; a failed transport or uncertain delivery still consumes it |
| Unspent attempts | Report as unattempted; forfeited for this campaign, never transferable to another run |
| Possible cumulative spending | At most 18 only after separate authorization; the current authorized ceiling remains 12 |
| Generation budget per attempt | At most 1,024 output tokens and 180 seconds total request wall time |
| Maximum proposed output allowance | 6,144 generated tokens across six attempts; this is a ceiling, not a target or present allowance |
| Benchmark / annotated-page / OCR / retrieval requests | Zero |

Health, template, tokenization and grammar checks must be nongenerating operations.
No generated warm-up, test completion, hidden diagnostic, repair call, external
model service or LLM judge is permitted. Expected values/statuses and this rubric
stay outside the model request. No request may include prior outputs, evaluator
fixtures, source labels, FinanceBench references, answers or justifications.

The five non-capacity questions and all source pages are unchanged. Capacity now
asks **“Calculate fictional Cedar Works' FY2031 quick ratio from this packet.”**
Its former availability/metaquestion remains preserved historically. Report this
task-wording change separately; do not present its before/after result as an
exactly matched question pair. The aligned instruction changes every prompt.

## Exact frozen identities

All hashes below are SHA-256. They identify the inspected contract and existing
runtime, not a new inference authorization. The entire historical v2 setup file
and its complete asset dictionaries are authoritative; a model name or backend
tag alone is insufficient.

| Identity | Exact value |
|---|---|
| Contract / case version | `typed-response-v3-offline / fictional-cases-v3-offline` |
| Offline implementation version | `bounded-answer-offline-contract-v3` |
| Verified Windows offline source fingerprint | `d3abdda241189dd1af5781499f9f052cf9cb00e566dab80d30288b2ae7dd0587` |
| Canonical schema identity | `bc759ce3837b6bd2353a52b92bb0bb206bd8240a17de71da8ac905d679e8519f` |
| Ordered wire-schema bytes | `3c09fec51d31962d78768f6ad3809abc9b6ad5fe8b8065197b2eec9133ac4076` |
| Effective ordered GBNF, 18,525 bytes | `dd3d90c3e13de2e852727aa6f49776edd6b6699b21d62ebdee65d5b69df60fce` |
| Logical instruction UTF-8 identity | `e01ebeb03de8d70e34e16f1d1706697a3842447b707f9e29734d4301c896d736` |
| Case/question/source specification | `610d5eff4a8157f9c031b99f5f69e3fc12aa73a3fdf0a2c4ae58b999441dab68` |
| Converter/backend commit | `a7a98e0fffed794396b3fbad4dcdbbc184963645` |
| Converter LF-normalized source | `1f6fee46d14f0b66f9e4150da8b17485534e544503d7898e72a4ebf1d3ed9c1d` |
| Existing model / official base revision | `Qwen/Qwen3-4B-Instruct-2507 / cdbee75f17c01a7cc42f958dc650907174af0554` |
| Local Q4_K_M GGUF, 2,497,278,880 bytes | `80f7dccce5ae984d2b40ba998871288e367fcb76a759f89c55e7139e4632f0e1` |
| llama.cpp b6500 Windows Vulkan server, 4,977,152 bytes | `62e6a5fec588ff3ea6d26a507db4373e56c850db19b39239bd30f5e7d87751cd` |
| Complete 37-entry backend_files dictionary, canonical JSON | `c636a424284ffd3941fb057c52461345a6fedd5475b3e5c3b9d23ff6097c801b` |
| Existing v2 setup file (historical, not a new seal) | `d1a496141c9de242034e5114ded3bc5500fb44afe92986d96c13bd94e9cc4774` |
| Existing .venv-answer freeze snapshot bytes | `34d53b3eb793a0244dfb55b559c865f5528aee4cb098fdb6f62f7cc063f27848` |
| Historical runtime packages dictionary, 44 entries, canonical JSON | `f8aaea30f337523f163defef1951974de9e46a66d92afc81dd660582dda84600` |

The environment is the existing review checkout's `.venv-answer`, Windows
`Windows-11-10.0.22000-SP0`, 64-bit Python **3.12.10**. Match its whole package
inventory, not only direct dependencies. Key versions: transformers 4.56.2,
tokenizers 0.22.2, Jinja2 3.1.6, torch 2.6.0+cpu, psutil 7.0.0. The CPU torch
package is not the generation backend; generation remains the pinned Vulkan
server. Official tokenizer/config/vocab/merges bytes must match
`ANSWER_SETUP_LOCK.json` and the saved v2 setup's `official_files` dictionary.
Do not reconvert, requantize, redownload or replace the local GGUF.

The recorded device is **Vulkan0 / NVIDIA GeForce RTX 3070 Ti / 8,192 MiB**,
driver **537.70**, as observed in the historical v2 memory log. Recheck this
condition prospectively; do not upgrade the driver or silently substitute a CPU,
CUDA backend or another GPU. Record fresh hardware and system inventory.

| Fixed execution setting | Required value |
|---|---|
| Context / slots | 6,144 tokens; parallel 1, one slot (`id_slot=0`) |
| Offload / KV | All 37/37 layers on Vulkan0; K=f16, V=f16 |
| Attention | Explicit Flash Attention off **and effective runtime disabled**; auto/enabled/unknown fails preflight |
| Other runtime | Batch 512, microbatch 128, threads 6; cooperative-matrix overrides disabled as in v2 |
| Context / startup | Context shifting off, no warm-up, no web UI; loopback server only |
| Decoder | Greedy: temperature 0, seed 0, top_k 1, top_p 1.0, min_p 0.0 |
| Penalties / cache | repeat_penalty 1.0, presence_penalty 0.0, frequency_penalty 0.0, cache_prompt false |
| Transport | One streamed `/completion` per case, exact ordered `json_schema` envelope; no retry middleware |
| Deadlines | Startup at most 180 seconds; each completion at most 180 seconds including stalled streaming |

Save the exact command and scoped backend environment. Match the v2 policy for
removing inherited LLAMA_ARG_/GGML_/CUDA_ overrides and disabling cooperative
matrices. Set offline/local-only asset access; use only a new campaign-local
transient cache if execution is later authorized. Keep all old cache roots intact.
Greedy seed-0 settings do not promise bitwise GPU determinism. No timing result
may be attributed solely to hardware or Flash Attention in this bundled repair.

## Prompt and packing controls

Allow only the fictional task/report IDs, original question and five source pages
with their literal text. Preserve zero-based page IDs **[0,1,2,3,4]**, in that order,
including blank pages. Each source-body prefix is at most 800 tokens, with the
existing truncation markers and no redistribution, selection or table repair.
The full evidence packet is at most 4,096 tokens, non-evidence overhead at most
1,024, complete rendered input at most 5,120; input plus allowed output is at most
6,144. Capacity must exercise exactly 4,096 + 1,024 = 5,120 input tokens, with five
800-token source prefixes. Preserve its existing deterministic padding procedure.

| Case | Input / evidence / overhead tokens | Prompt UTF-8 SHA-256 | Canonical token-ID-list SHA-256 |
|---|---|---|---|
| signed | 620 / 69 / 551 | `2ddcfccbfc5128aa524244487fa127b1e31074331cd8af5df0f57975375039be` | `5ee0bcd96848ef50326a692ca012117e9a86cb1e43ee4e7f2e9b18bf9d4027e5` |
| scale | 613 / 65 / 548 | `def227c160b34771e2d9eb8985cceb73c7142c3641ff1bdef16409aec32a1a6a` | `9eb5c8da82b0386f3271f798aa96e4110987b5c859c2a13e22dbec91b30363bc` |
| margin | 644 / 87 / 557 | `7426ad6d90a5267d8b68cc7ef71d244b2b854f41d43d425aefc0ae7802cbf2ce` | `7e2055e24967a7f6ba23ec5d6d8534d73fe37631cf073f83efcaaf391e8f8783` |
| comparison | 636 / 86 / 550 | `331562062492f226ab2c09a95bb746bfe44d4b992e05a1c6e81980cb1403782c` | `404d24128d09e468e6a654781b4c14179bd0468204403590c4c6d89a06f848f4` |
| missing | 623 / 77 / 546 | `80a7e7be454e2a1793e2533dd396464eea520488e4f8e8622d7fbdb7248fe059` | `020fa8a52ebf2b28c0acb5e06b8c1ba860d5ab5c24d1aed23137999eb6c549ac` |
| capacity | 5120 / 4096 / 1024 | `6c6a551937058563ff98c3d25caa14640dfe27d4352a1f302405fcf9ec1e7485` | `6a7eaa8f3858c5b84ff0489e652b4a1e76a617cbf5ed7ef4c488293ee96c514f` |

These are the verified **local-tokenizer identities**, not yet new server runtime
observations. Before any future completion, the same backend's nongenerating
template and tokenize operations must reproduce every prompt byte/token sequence.
Save the full tokens, retained intervals and underlying page-text hashes, not just
counts. Do not revise a prompt or discard a page to make a preflight pass.

Status must be first in the actual nested wire schema and generated branch.
Quantity discriminator order and unit/currency/scale alternatives stay fixed.
Retain the exact `json_schema` transport path, ordered wire serialization and
unchanged scoring; do not silently substitute a different grammar/API condition.
Verify the pinned native converter's ordered effective grammar against the frozen
18,525-byte GBNF, and retain converter/server identities and the full request
bytes. An order-insensitive schema digest alone cannot establish this identity.

## Evaluator-only criteria, frozen before seeing new outputs

The current validator remains unchanged. No coercion, missing-field filling,
numeric-prefix stripping, unit/scale rewriting, invented operands, dropped extra
claims, quote correction or citation repair is allowed. Parser support for valid
signed/grouped/parenthesized numbers follows the existing strict implementation.
Keep source quantities' declared dimensions/periods, the existing `quantum=0.01`
and Decimal ROUND_HALF_UP comparison policy, and exact independent arithmetic
recomputation. Do not introduce a blanket relative-error tolerance.

| Axis | Separate acceptance criterion |
|---|---|
| Contract conformance | All six complete responses are one strict JSON object; duplicate/nonfinite/malformed values rejected; exact schema and grammar; status/answer/claims/calculation/missing-facts invariants agree; typed dimensions valid; required named operands/results represented |
| Numerical correctness | All requested components on the four numerical tasks pass period/sign/value/unit/scale/completeness checks; every submitted expression independently recomputes correctly with source-linked named operands; correct digits cannot excuse a wrong formula or unsupported inputs |
| Source support | Every asserted claim, source quantity and derived result is supported by the exact retained packet; page/span literal matching plus manual entailment; derived results cite their underlying facts, not an invented computed quote; abstentions correctly describe absent facts |
| Interpretation | Answer addresses the requested metric, year and scope; percent versus percentage points, cash flow versus profit, signs, direction and abstention meaning are correct; no contradictory prose, invented causal claims or unrequested aggregation |
| Resource feasibility | All six complete within fixed caps/deadlines on the verified runtime, no OOM/fallback/truncation or monitoring failure, and the prospective resource limits below hold; quality success cannot substitute for resource evidence |

Numerical scores have denominator **four numerical cases**, with required
components also reported individually. `missing` and `capacity` are N/A for
numerical-result accuracy, not two easy numerical successes. Contract, support,
interpretation and completion are evaluated on all six, with abstention-specific
support rules. Keep generic mechanics and case-specific checks separately visible.
A mechanically valid response is not automatically fully supported.

### Case-specific manual checklist — evaluator only

| Case | Required source-checked behavior |
|---|---|
| signed | Answered: FY2031 operating cash flow **−12.5 USD million**; parentheses preserved as negative; literal p=0 support. Calculation null or a valid named identity; no invented cash inflow |
| scale | Answered: FY2031 **1.25 USD billion = 1,250 USD million**; source operand and requested typed converted result; named source-linked conversion with an allowed numeric constant, not an undefined `scale_factor` quantity |
| margin | Answered: FY2031 revenue **240**, cost of sales **180 USD million**; FY2030 margin **20 percent**, FY2031 margin **25 percent**, change **+5 percentage points**. Current-margin calculation must use the proper named revenue/cost operands. Independently recompute `(240−180)/240×100` and `25−20`; the latter requires manual review because the contract holds only one calculation object |
| comparison | Answered: operations **+40**, investing **−12**, financing **−9 USD million**, FY2031; operations supplies most cash. Profit **declined**, with the stated higher-input-cost explanation; higher revenue is not higher profit. Calculation null; no invented cash-flow total |
| missing | Strict insufficient_evidence: current liabilities are missing. Do not assume zero or invent a quick ratio. Identify the missing denominator, preserve that cash/receivables were supplied; claims/quantities empty and calculation null |
| capacity | Same strict abstention to the prospectively clarified calculation question. The retained pages lack current liabilities and sufficient quick-asset facts; filler is not financial evidence. No ratio, invented facts or answered prose contradicting abstention; explicit relevant missing facts |

Literal but irrelevant quotes fail source support even if mechanics pass. Correct
final numbers with wrong business operands/formulas fail interpretation/support.
Extra unsupported figures or claims fail; reviewers may not ignore them. One
calculation object does not establish automatic validation of the second margin
derivation. These limitations are explicit, not excuses to waive a component.

Two human reviewers independently inspect all six raw responses against the
exact packed excerpts and this frozen rubric, without seeing each other's scores
or the automated pass/fail first. Where practical, hide campaign labels. Record
pass/fail/N/A for each axis, every issue, page/span, recomputed values, rationale,
reviewer ID and date. Then reconcile differences in a separate adjudication record
without replacing either original rating. An unresolved or unreviewed applicable
facet prevents qualification. No LLM judge or generator-created reference key.
These are already inspected development cases; reviewer masking does not make
them held-out data.

## Prospective resource gates

The following are proposed **new qualification limits**, not claims that the old
runner enforced them. Before model startup require at least 5 GiB free output-disk
space, 2 GiB system-available RAM and device-wide VRAM use below the limit below.
During startup and every completion require:

- device-wide sampled used VRAM at most **7,168 MiB** on the 8,192 MiB device;
- sampled server+client RSS at most **8 GiB**, and system-available RAM at least
  **2 GiB**;
- no OOM, driver reset, CPU offload/fallback, unexpected runtime transition,
  context overflow, output-limit termination, truncated/empty response or deadline;
- timestamped server/client RSS and whole-system availability sampled at the
  existing 0.25-second interval, device-wide `nvidia-smi` at the existing 1-second
  interval, with observations bracketing every completion and no measurement
  errors or unexplained coverage gaps.

Save server OS peak working set, sampled RSS/VRAM, total/available memory and
driver/device readings; report startup, packing/preflight and per-case wall time,
prompt/decode tokens and backend timings separately. A successful ordinary case
does not waive the capacity case. Sampling can miss peaks; device-wide VRAM
includes the display and other processes, and summed RSS can double-count shared
pages. Do not call these exact isolated peaks. A short capacity abstention checks
5,120-token input capacity with an allowed 1,024-token output reservation; it
does **not** demonstrate sustained generation of all 1,024 tokens. Do not add a
request to force that measurement.

## Pre-execution gates and stop rules

The current entry points remain paused and intentionally retain the historical
v2 lifecycle. **Removing a pause guard is insufficient and must not be the future
implementation.** A separately reviewed incremental implementation would need
an explicit v3-only path, all six revised prompt controls, unchanged evaluator,
single-use durable attempt charging, terminal no-retry behavior and resource-stop
enforcement. Demonstrate these offline with mocked transports before requesting
authorization; do not install anything or execute that work under this plan.

Before a future authorization request, freeze that implementation's commit plus
dirty-file/per-file manifest and exact source fingerprint. That future runner
fingerprint is **not yet defined**; do not copy the current offline fingerprint
onto changed code or invent an executable setup identity. Preserve all current
contract/grammar/prompt/token identities above; any substantive drift requires a
new reviewed plan. The sole intended request changes relative to historical v2
are this bundled contract/instruction/ordered-schema repair and capacity wording.

The future sequence is explicit:

1. Review a passing offline implementation, freeze the evaluator/manual rubric,
   planned asset/runtime identities, local prompt/token controls and grammar,
   and confirm matching original preservation snapshots.
2. Obtain separate explicit authorization for **one** at-most-six-attempt campaign.
   Only then create its single-use setup/ledger/cache/run directory.
3. Start the owned server without warm-up; verify actual runtime/resources and all
   six backend template/token controls before any completion. A preflight failure
   terminates this campaign with zero completion attempts; it grants no restart.
4. Charge and submit the fixed sequence subject to the stop rules below.

Nothing here performs these stages, creates their execution objects or grants
authorization. The current pause remains unconditional.

| Trigger | Required action in any later authorized campaign |
|---|---|
| Existing campaign/output/ledger; history mismatch; asset/code/runtime/driver/contract/token drift; missing source page; leaked evaluator data; preflight resource failure | No completion; retain preflight evidence and terminate the campaign attempt. Do not delete/reseal/restart to bypass the gate |
| Transport failure, timeout, cancellation, uncertain delivery, process crash, monitor failure, resource-limit breach or output truncation/limit | Charge the started request, retain partial bytes/logs, stop the owned server and campaign; mark remaining cases unattempted; no retry or resume |
| Invalid JSON/schema or output outside the frozen grammar | Retain bytes, fail contract conformance and stop: grammar enforcement/interface is not demonstrated. Do not repair and continue |
| Schema-valid wrong number/year/sign/scale, undefined operand, incorrect arithmetic, false abstention, literal-support or interpretation failure | Record every failure. The fixed remaining sequence may continue solely to characterize the predeclared cases while runtime/resource/preservation gates hold; no change to inputs or scoring. Overall qualification is already failed |
| Manual disagreement or incomplete manual review | Preserve separate ratings; qualification pending/fails to establish success until adjudicated. No inference is added to resolve disagreement |
| Preservation mismatch at any point | Stop, preserve evidence and identify the changed artifact; never overwrite history with a repaired snapshot |
| Six attempts completed, or any terminal stop | Close the single campaign and stop. Unused potential attempts do not authorize another campaign or a new ticket |

If a crash occurs after durable charging but before delivery is known, conservatively
keep that attempt spent. No automatic fallback, output repair, adaptive prompt,
model/quantization/FA sweep, changed tolerance or borrowing of future benchmark
requests is included.

**Qualification succeeds only if all six complete and every applicable contract,
numerical, support, interpretation and resource facet passes, both manual reviews
are resolved, and preservation passes.** Report each axis even on overall failure.
A stopped campaign cannot qualify; keep attempted/completed/unattempted counts
visible rather than shrinking the denominator to successes.

## Preservation, export and interpretation of any future evidence

Before and after any later authorized execution, compare the exact same protected
file set, including detection of additions/deletions within both historical run
trees. Preserve both complete raw run directories, setup files and exhausted
ledgers, original archives/patches and review/results documents. Preserve `.venv`,
`.venv-ocr`, any `.venv-ocr-gpu`, `.venv-answer`, model/official/backend assets,
source PDFs/rendered images, OCR raw outputs/caches and retrieval outputs. No
operation touches the other machine's runs. Use package inventories plus relevant
binary/config hashes; retain the existing cache manifests and any available
content-hash inventories without claiming they cover absent remote caches.

Expansion v1 remains frozen at k=5: same questions, scoring, tokenization,
full-report page candidates, rankings and zero-based page IDs. No OCR/retrieval
tuning or FinanceBench generation is part of this qualification.

A future export must be a new, separately named archive with:

- plan/rubric version and hash, explicit later authorization reference, final
  implementation/per-file fingerprint, immutable model/backend/environment
  manifests, exact command and observed runtime;
- before/after preservation files and comparison result, campaign ledger with
  charge times and every attempted/uncertain/unused case, linked hashes for both
  exhausted controls; no reset historical counters;
- for every attempted case, question/source page identities, exact packed prompt
  bytes and token IDs, page order/retained intervals/truncation flags, ordered
  request bytes, raw SSE (including partial streams), extracted raw content,
  parsed object or parse error, terminal backend record, strict diagnostics;
- startup/server logs, full timestamped resource samples, per-case timing and
  termination reasons, all failures and unattempted cases;
- both original human scoring records plus adjudication, separate axis/component
  tables, a complete relative-file SHA-256 manifest and archive checksum. Check
  archive integrity and extracted hashes offline before interpreting results.

Do not overwrite a raw response to add a corrected version, and do not put this
evaluator-only document in a prompt export allowlist. Preserve canonical request
identity separately from ordered wire-byte identity. No original run or ledger
is migrated, rescored or rewritten as the proposed condition.

Compare the five unchanged questions case by case against saved v2, retaining
both gains and regressions on every axis. Show capacity in a separate changed-task
row. An old already invalid response stays a historical failure; a new correct
response cannot repair it. Do not attribute any difference to one interface change
or compare latency as an isolated FA/hardware experiment.
Use original v2 mechanical diagnostics and the already verified source review;
mark a historical facet that was not recorded as unavailable. Do not apply the
new representation requirements retrospectively and call that an original score.

Even prospective 6/6 success establishes only that these inspected synthetic
development checks can pass under the repaired contract. It is neither a
generalization estimate nor FinanceBench accuracy, and grants no benchmark
generation allowance. The private FinanceBench rubric/source holds and any future
answer-generation design remain separate decisions.

**Current outcome:** Windows offline conformance evidence verified; prospective
qualification specified; no new inference or allowance; 12 spent, 0 authorized
remaining. Historical v2 stays 1/6.
