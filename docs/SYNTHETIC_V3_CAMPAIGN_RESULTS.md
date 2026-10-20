# Authorized synthetic v3 campaign: verified offline results

Review date: **2026-10-20, America/New_York**. Reviewer: **AI-assisted offline evidence and semantic review**. This document is not an independent human rating or adjudication.

**Decision: the campaign demonstrates structural output conformance and sampled runtime feasibility, but fails the frozen answer-quality gate. Do not advance this generator condition to FinanceBench.** All six responses conform structurally; only `missing` and `capacity` pass the unchanged case-specific mechanical checks. The four answerable numerical cases all fail their required typed-quantity checks. Three unnecessarily abstain. Independent human review remains pending.

This review performed no inference, model/backend initialization, tuning, package or source change, patch, new allowance, or FinanceBench generation. Original responses, scoring files, ledgers, preparation, authorization, archives and expansion v1 remain unchanged. New review files are separate artifacts.

## 1. Evidence, integrity and authorization

The three supplied ZIPs were read from their attached local copies. ZIP CRC checks pass; each archive has an exact, duplicate-free inventory matching its export manifest; every exported content digest recomputes. Counts exclude the embedded export manifest.

| Attached archive | Content files | Independently recomputed outer SHA-256 |
|---|---:|---|
| `qualification-authorized-20261019-operator-evidence(1).zip` | 16 | `e3ad775d41f127fb774156414c2d76b9da09fab83e2989d016cd6c84475215eb` |
| `qualification-authorized-postrun-20261019-review(2).zip` | 15 | `9d78cb15163a99f7fdad05c2d84086e5f3520910d65515b43b631c18aab49997` |
| `synthetic-contract-v3-qualification-evidence(1).zip` | 213 | `e9e4e5678f46d5675e12c4007d80dd620afe7dd1fab91c7c17ae85ac3ed83142` |

All **244 content files** pass their respective manifest checks. The campaign ZIP hash also matches the exported CLI result in the operator console; the preservation ZIP hash matches the captured preservation result. No separate outer-hash sidecars were attached. These checks establish the supplied exports' internal integrity and cross-record consistency, not independent filesystem-wide or network-wide attestation.

The campaign retains the exact final preparation, the external authorization and approval pin, the verified binding identity, and the frozen plan/rubric. All **18 authorization bindings** reconcile with the reviewed values, preparation, frozen reference, and previously reviewed native-build evidence. The four final Windows identities are:

| Identity | SHA-256 |
|---|---|
| Implementation file-map fingerprint | `3b86653a204f349bfcc43cb6a044aa9fc23a2ba96ab1ff729d44c7aae16c9a41` |
| Complete implementation record, canonical | `6d45308d47c93579bd99ad01a8214dc3703801095005f63baf5058b5195974d2` |
| Preparation, exact file bytes | `5c96fcc6cb3311c2b1e5bf8feec4f33c8c2da1110b6a9c5ccf9cb45740d668bc` |
| Preparation, canonical object | `c00e0fab3ece81ad0cb503af9a54bfca51161480d0a9241d3e59ad2d5c3bcd9f` |

The raw authorization hash is `1394d5deadd108774d9b90eceb212a544a1ae18b2e49aec809cc7e7346988ba5`; the raw approval-pin hash is `7c32528846507698ec14ac07e22fa38e8c9cd1101f3f52c7aceabfa5b5f86095`. The pin matches the exact authorization bytes and fixed external path. The claim, run manifest and verified-binding copy contain the same identity and limits.

The filenames preserve the 20261019 campaign designation. **Execution actually occurred on October 20**, not October 19. Authorization was issued at 21:36:12.956009Z and pinned at 21:38:35.557810Z; expiry was 22:36:12.956009Z. The journal runs from 21:40:04.881007Z through 21:41:07.221066Z, or about **17:40–17:41 EDT on October 20**. Every recorded charge and terminal event lies inside the authorization window. The reference to the user's October 19 consent is consistent with later issuance and execution.

Operator evidence also records 24 external helper tests passing in 0.757 seconds without skips, followed by successful scope preflight, record issuance, pinning and read-only verification. Those are offline setup checks, not additional model requests. The retained 88-test host log and earlier 338-test Windows results remain historical offline validation; they were not rerun as model experiments by this review.

## 2. Attempt accounting and terminal outcome

The journal contains 14 events: one claim, six alternating durable charges and finished records, and one terminal record. Its sequence numbers and SHA-256 chain reconcile. Every charge precedes its corresponding recorded submission start and binds the saved request bytes. The finished outcomes equal the six manifest records.

| Accounting item | Verified result |
|---|---:|
| New campaigns | 1 |
| Charged completion attempts | 6 |
| Recorded submission attempts | 6 |
| Responses received and retained | 6 |
| Unfinished/uncertain attempts | 0 |
| Unattempted cases | 0 |
| Remaining authorized attempts | **0** |
| Historical v1/v2 requests, preserved | 12 |
| Cumulative charged attempts | **18** |
| FinanceBench requests in this campaign | 0 |

Fixed order is `signed`, `scale`, `margin`, `comparison`, `missing`, `capacity`. Backend logs show six `/apply-template`, six `/tokenize`, then exactly six `/completion` POSTs, all HTTP 200. Health polling before readiness is nongenerating. There is no logged extra completion, warm-up generation, retry or second run in the supplied evidence. The fixed campaign anchor is consumed; no restart or resume is permitted.

Continuing the fixed sequence after the case-mechanical failures complied with the frozen rules: those responses remained schema/grammar-valid and no terminal transport, identity or resource condition was recorded. This was not a retry or an acceptance of the failed answers.

The saved CLI exit is **6**, matching `completed_mechanical_failures_manual_review_pending` with a verified export. This is distinct from the preservation tool's successful exit 0. The automatic manifest correctly retains `automated_checks_pass: false`, `qualification_pass: false`, and pending two-human review. The initial run manifest precedes export; export status appears in the console result, not in that earlier manifest. Their contents reconcile when that added export field is excluded.

## 3. What passed, and what did not

| Axis or diagnostic | Result | Meaning |
|---|---:|---|
| Strict JSON, frozen schema and effective ordered grammar | **6/6** | Structural conformance only |
| Generic response invariants/mechanics | **6/6** | No generic parser/type/invariant issue; not a source-correctness result |
| Frozen case-specific mechanical validation | **2/6 (33.3%)** | Only `missing` and `capacity` pass |
| Expected answer/abstention status | **3/6** | `signed`, `missing`, `capacity` choose the expected branch |
| Complete required typed-quantity checks, numerical tasks | **0/4** | All answerable numerical tasks fail their required components |
| Required typed-quantity components | **0/10** | One signed, one scale, five margin, three comparison components |
| Unnecessary abstentions | **3/4 answerable cases** | `scale`, `margin`, `comparison` |
| Expected abstentions | **2/2** | `missing`, `capacity`; numerical-result accuracy is N/A |
| Calculation objects returned | **0** | Both required calculation tasks lack a calculation; no arithmetic execution accuracy can be estimated |
| Source support and interpretation | Human review pending | AI-assisted findings below; literal checks are insufficient |
| Runtime/resources | Passed observed gates | Scoped to this run and sampled evidence |

All saved generic and case-specific reports were independently reproduced using the unchanged, hash-matching evaluator and the exact retained source pages. Raw SSE re-parses to the exact saved content and backend-final records. No coercion, repair, new tolerance or rescoring was used. Each raw response also passes the frozen grammar recognizer, and each server-returned effective grammar is byte-identical to the frozen **18,525-byte** grammar, SHA-256 `dd3d90c3e13de2e852727aa6f49776edd6b6699b21d62ebdee65d5b69df60fce`.

The **0/4** figure is the complete typed numerical-task result under the existing requirements, not a statement that every digit the model produced was wrong. `signed` gives the correct scalar `-12.5`, but its quantity is not the requested monetary amount. The other three tasks omit the required typed results through abstention. None of the six outputs supplies a calculation, so this campaign does not measure how reliably the model executes a valid submitted arithmetic expression. Missing/capacity are not counted as easy numerical successes.

Every saved `fully_supported_pass` remains false pending semantic review. This report does not replace those fields with AI judgments.

## 4. Case review: measured checks and AI-assisted interpretation

| Case | Generated status | Structure | Frozen mechanics | AI-assisted finding |
|---|---|---|---|---|
| signed | answered | Pass | Fail | Correct negative digits, wrong quantity dimensions and inadequate citations |
| scale | insufficient_evidence | Pass | Fail | Unnecessary abstention despite a supported source value and permitted conversion |
| margin | insufficient_evidence | Pass | Fail | Incorrectly describes supplied operands/prior margin as missing |
| comparison | insufficient_evidence | Pass | Fail | Acknowledges source facts but denies their straightforward comparative meaning |
| missing | insufficient_evidence | Pass | Pass | Appropriate missing-denominator abstention; human confirmation pending |
| capacity | insufficient_evidence | Pass | Pass | Appropriate missing-denominator abstention at maximum input; human completeness review pending |

### Signed extraction: digits correct, financial quantity and evidence wrong

Retained p=0 says: `Cedar Works FY2031. Operating cash flow: (12.5) USD million.` The source therefore supports **−12.5 USD million**, FY2031. The answer string is `-12.5`, and the claim correctly restates the parenthesized source amount. The sign was read correctly.

The typed quantity instead uses `unit: percent`, `currency: none`, `scale: unit`. Those fields form a valid dimensionless quantity under the schema; they do not describe the money in the question/source. The frozen quantity check therefore fails unit, currency and scale-adjusted final-number comparison while passing the fiscal year and sign checks. Its `unit_scale_valid: true` means the declared scale is recognized, not that it is the correct financial dimension. The unchanged case check records `required_quantity` and `unsupported_quantity`.

Both the claim and quantity cite `{page_id: 0, span: "0"}`. The character `0` occurs in `FY2031` on the included page. The frozen `citation_check` accepts any nonblank whitespace-normalized literal substring on a valid page, so both pointers pass the literal check. That single character establishes neither the operating-cash-flow amount nor its unit/sign. This is **not an off-by-one page-ID error**: page 0 is the correct page; the selected span is non-probative.

The model made the wrong financial-type selection and provided inadequate evidence pointers. The generic validator's acceptance is an intended limitation of its literal predicate, not proof of entailment. The case-specific monetary check still rejects this response. Preserve both the mechanical failure and the literal-check pass; do not retroactively tighten the citation rule or call the output supported.

### Scale conversion: available value, unwarranted abstention

P=0 directly supplies **1.25 USD billion**. The task asks for USD millions: independently, `1.25 × 1000 = 1250` USD million. This is evaluator-side reference arithmetic, never a new model output.

The response says the conversion is not explicitly supported in the required claim/source format and treats the absence of a directly printed converted value as missing evidence. The frozen instruction already permits numeric conversion constants, requires named source operands, and tells derived figures to cite underlying facts rather than invent a quote containing the calculated result. A printed “1,250” is not required for the conversion to be answerable.

The response has no quantities or calculation. Its unchanged failures are wrong expected status, missing required quantity, and missing source-linked conversion. Its initial restatement of 1.25 billion is accurate; its justification for abstaining is not supported by the task/instruction. It is not an arithmetic miscalculation because no calculation was attempted.

### Margin and percentage-point change: no missing source operands

P=0 supplies FY2031 revenue **240 USD million**, cost of sales **180 USD million**, and FY2030 gross margin **20 percent**. Independent source arithmetic yields `(240−180)/240×100 = 25 percent`, then `25−20 = +5 percentage points`.

The response lists the FY2031 revenue/cost details and FY2030 margin among missing information even though all are present in the short retained paragraph. The current margin is a requested derivation, not an absent source operand. All five required quantities are omitted and calculation is null. Frozen failures are wrong expected status, five missing/incorrect required facts, and absent gross-margin calculation.

This is an evidence-use and task-interpretation failure, with numerical nonresponse. There is no submitted arithmetic to verify. The second change derivation would still require separate human checking even if a future output supplied the contract's single calculation object; this run supplies neither derivation.

### Cash-flow/profit comparison: source acknowledged, implication rejected

P=0 provides operations **+40**, investing **−12**, financing **−9 USD million**, and explicitly says profit declined because input costs increased. Operations is the largest cash source whether comparing signed flows or absolute magnitudes. Profit did not improve.

The response repeats the cash-flow figures in `missing_information`, then calls the comparison ambiguous. It also quotes the statement that profit declined but denies that improvement/decline can be determined. Those rationales contradict the retained packet's directly stated facts and simple comparison. Merely placing assertions in `missing_information` does not make them semantically correct.

The response omits all three typed quantities and gives the wrong expected status. No unrequested aggregate calculation is produced. This v3 response does **not** contain a newly generated positive financing quantity: the historical financing-sign failure is not a new v3 quantity error. It is now a failure to answer and represent the signed alternatives at all. The prose's mention of the source figures cannot substitute for the required answer and typed fields.

### Missing denominator and capacity: retain the mechanical passes

`missing` supplies cash 10 and receivables 5 USD million while explicitly withholding current liabilities. The response correctly identifies current liabilities, uses the strict abstention marker, and leaves claims/quantities empty and calculation null. It neither assumes a zero denominator nor invents a ratio. Its semantic acceptability appears consistent with the frozen rubric, subject to independent human review.

`capacity` asks the prospectively clarified calculation question and retains five 800-token source prefixes. Each starts with the statement that current liabilities were not supplied; the remaining body is filler. The response correctly abstains and identifies that missing denominator. It does not explain the additional absence of sufficient quick-asset facts; reviewers should assess the rubric's missing-fact completeness without inventing a new retroactive mechanical requirement. Its saved mechanical pass stands. A successful abstention on long repeated filler establishes neither long-document numerical reasoning nor real-report table understanding.

### Failure attribution and unresolved hypotheses

The three unnecessary abstentions cannot be explained by missing retrieval hits, page-number shifts, clipping of those short sources or output truncation. All relevant facts are present on p=0; none of the five non-capacity packets is truncated. The observed Flash Attention setting and resource readings provide no evidence of an execution failure causing these answers.

The prompt's source-only discipline may have encouraged excessive caution, and the long typed interface may have increased response burden. These are **hypotheses**, not findings about why the model chose these branches. The contract expressly permits derivation and the required facts are available, so no newly identified contract contradiction justifies accepting these outputs. One bundled development campaign cannot separate instruction effects, grammar effects, checkpoint ability, quantization effects or decoding behavior. No logit/branch-probability evidence or matched causal intervention was collected.

No defect was found that invalidates the reproduced **6/6 structural, 2/6 case-mechanical** result. The implementation does have declared coverage limits: substring checks do not test entailment; no citations in a valid abstention make literal-citation checks pass vacuously; generic missing-fact validation checks nonblank text rather than truth. A semantically wrong financial type can satisfy schema dimensions. These limits explain why generic mechanics passes 6/6 while task mechanics and semantic review identify failures. No rules were changed in this review.

## 5. Frozen inputs, backend and measured resources

The generation condition is the existing **Qwen/Qwen3-4B-Instruct-2507**, official revision `cdbee75f17c01a7cc42f958dc650907174af0554`, local Q4_K_M GGUF, using llama.cpp **b6500 / a7a98e0fffed794396b3fbad4dcdbbc184963645**, Windows Vulkan. Bound model SHA-256 is `80f7dccce5ae984d2b40ba998871288e367fcb76a759f89c55e7139e4632f0e1`; bound server SHA-256 is `62e6a5fec588ff3ea6d26a507db4373e56c850db19b39239bd30f5e7d87751cd`. The full runtime binding is `5558959afa2db9b7dda7f79308858f4aa63ab7168dd38eaa4e87d28663f54ba6`.

Preparation retains Windows 11 10.0.22000, Python 3.12.10 and the fixed 44-package answer environment. Runtime logs and samples identify RTX 3070 Ti, Vulkan0, 8,192 MiB, driver 537.70. The log confirms **37/37 layers** offloaded, context 6,144, one sequence/slot, batch 512, microbatch 128, six threads, f16 K/V, and **Flash Attention explicitly and effectively disabled**. A CPU backend DLL also being loaded is not evidence of CPU fallback; actual model offload is separately confirmed. No device loss, OOM or model-offload fallback is indicated.

Requests are exact ordered serializations of the frozen payload: seed 0, temperature 0, top_k 1, top_p 1, min_p 0, repeat penalty 1, presence/frequency penalties 0, cache_prompt false, n_predict 1,024. Server-returned settings agree. Every final response ends with EOS, has `truncated: false`, and is below the output limit. Backend timing reports `cache_n: 0` and full expected prompt processing; a final `tokens_cached` count is slot occupancy after processing, not a cross-case cache hit.

All saved prompts, token-ID arrays, page IDs, retained intervals, source/question digests, raw request hashes and native wire schemas reconcile with the final preparation and frozen controls. Counts remain **620, 613, 644, 636, 623, 5,120**. Page IDs remain **0–4**, including blank pages. Capacity is exactly 4,096 evidence + 1,024 overhead tokens with five 800-token bodies and its frozen deterministic padding. The backend controls precede every completion. Raw metadata responses are not saved separately; parity is supported by the successful control gate, full saved local inputs and the twelve corresponding logged metadata calls.

The fictional request path contains only its fixed instructions, task/question/report excerpts and schema. Evaluator facts, expected answers and review scores remain outside the request. This campaign does not run PaddleOCR or FinanceBench retrieval; it cannot be used to measure an OCR-to-answer effect.

| Resource observation, independently recomputed | Observed | Frozen bound |
|---|---:|---:|
| Sampled server + client RSS peak | **3.073 GiB** | ≤8 GiB |
| Sampled server RSS peak | 2.784 GiB | Included in sum bound |
| Sampled client RSS peak | 0.292 GiB | Included in sum bound |
| Server OS peak working set | 2.822 GiB | Additional process measurement |
| Minimum system-available RAM | **5.684 GiB** | ≥2 GiB |
| Whole-device sampled VRAM peak | **4,008 MiB** | ≤7,168 MiB |
| RAM samples / GPU-containing samples | 112 / 32 | Nominal 0.25 s / 1 s plus brackets |
| Largest observed RAM / GPU gap | 0.531 s / 1.360 s | <6 s lost-coverage stop threshold |
| Measurement errors | 0 | None permitted |
| Startup | **3.172 s** | ≤180 s |
| Longest completion wall time | **7.500 s** | ≤180 s per request |

All twelve request-boundary samples are present in the retained sample series. These are sampled whole-device VRAM and process working-set measurements, not isolated model VRAM or a guarantee that instantaneous peaks were observed. RSS sums can double-count shared pages.

The unchanged preflight enforces at least 5 GiB free disk and a successful campaign implies that gate passed. **No fresh numerical disk-free value is retained for the live campaign.** The preparation's approximately 275.28 GiB is an earlier offline setup reading; it must not be relabeled as the minimum during generation. Disk is not continuously sampled. Complete model weights, backend binaries, environment binaries and OCR payloads are not included in these review ZIPs, so their live checks are supported by the retained bindings/preservation records rather than a new rehash on this review host.

## 6. Timings and workload

| Case | Input tokens | Output tokens | Request wall (s) | Backend prompt (s) | Backend decode (s) |
|---|---:|---:|---:|---:|---:|
| signed | 620 | 193 | 2.656 | 0.937 | 1.675 |
| scale | 613 | 152 | 2.140 | 0.793 | 1.305 |
| margin | 644 | 93 | 1.703 | 0.864 | 0.807 |
| comparison | 636 | 246 | 2.968 | 0.791 | 2.129 |
| missing | 623 | 62 | 1.610 | 1.030 | 0.538 |
| capacity | 5,120 | 57 | 7.500 | 6.761 | 0.691 |

Total generated tokens: **803**. Summed completion wall time: **18.577 s**. Validation/repacking: **19.422 s**. All-six metadata controls: **0.547 s**. These timings describe the actual responses, including wrong abstentions; short, failed answers must not be represented as efficient correct reasoning.

The manifest's `wall_seconds` is **48.234 s**, but the source sets that timer before post-run preservation/asset hashing, terminal journaling and ZIP export. Claim-to-terminal event elapsed time is **62.340 s**, still excluding subsequent export. Neither is an independently measured end-to-end operator wall time. Do not attribute differences from earlier campaigns solely to hardware, grammar or Flash Attention; workloads and the bundled contract/prompt condition changed.

## 7. Preservation and historical comparison

Run preservation-before equals preservation-after across **204 protected roots**, resolving to **272 unique file identities**: the preparation's 201 roots/269 files plus the exact preparation file and two new approval files. All original **184 tracked file hashes** are contained and match the postrun recapture.

The postrun comparison independently matches the original before inventory after normalizing hash-letter case and BOM/newline representation. It is not byte-identical inventory text; the underlying paths and digest values agree. All three package inventories match their original package lines: baseline **7**, CPU OCR **67**, answer **44**. Inventory commands return 0 with empty stderr. Their raw files differ in BOM/newline representation; no package-line difference is present.

The separately saved before/after inventories for the two earlier review directories and archives are identical and agree with the run's protected inventory. Original implementation/compiler archive identities remain `36b338daed91b607024c3dd9cbd1c831e5c8bf269ecfff05b73126b2f7ef07ad` and `44c2558b2158259eb94b0664fd6bd012eaefb4462f464fc85f47e1e99c1b1913`. The historical v1/v2 setup/run/ledger identities remain bound, with twelve historical requests spent and v2 still **1/6**, only `missing`. The operator-delivery files match their original delivery hashes. The frozen source/Git state on this review host also still matches its saved delivery identity.

The new result is **2/6**, adding the mechanically valid capacity abstention to missing. This is a descriptive development comparison, not evidence that one isolated repair caused an accuracy gain. V3 changed the contract serialization/instruction and clarified capacity from an availability/metaquestion to a calculation request. Its question is not an exactly matched before/after item. No numerical task is newly successful under the frozen complete requirements.

Preservation evidence covers the specified files, trees and package inventories. It does not establish that every OCR-cache payload or installed binary was independently rehashed for this review. The existing native/CPU-OCR/GPU-OCR pilot and frozen expansion-v1 k=5 retrieval control remain the completed research baseline; these synthetic outputs do not revise that pilot's metrics.

## 8. Human review and next research decision

**No independent human ratings or adjudication are included.** The retained manual template is blank, and the manifest correctly remains pending. This AI-assisted review does not count as either required human reviewer and must not be entered into their original rating files.

Give two reviewers separate blank templates, raw responses, exact packed excerpts and the frozen rubric. Preserve their initial independent ratings before showing each other's ratings or automated diagnostics. This report contains both diagnostics and AI interpretations and should therefore be withheld from their first-pass packets. If a reviewer has already seen them, record that disclosure rather than claiming blind review. Preserve both originals and a separate adjudication; append a separately named final evaluation summary and reviewed export without changing raw outputs, historical scores or the initial export.

Reviewers must separately assess financial units/scales/signs/years, every requested component, formula/operand validity, exact-span support and entailment, source claims embedded in abstention explanations, and proper abstention. They should specifically examine the signed response's dimension/citation mismatch, the three false missing-evidence rationales, and capacity's missing-fact completeness. All applicable criteria must pass to qualify; the existing mechanical failures already block qualification even while this semantic review is pending.

**Recommended research decision now:** close this authorized campaign as an unsuccessful answer-quality qualification, retain v3 as the failed development control, and keep FinanceBench generation paused. Resource feasibility alone is not a reason to proceed. Continue to report the already completed matched native/OCR retrieval pilot using expansion v1 at k=5.

After the human reviews are reconciled, the next useful prospective design is a **matched response-contract burden comparison**, rather than another uncontrolled repetition of these six cases. It would ask whether the same frozen model/runtime can give correct concise answers with exact supporting excerpts when it is not simultaneously required to populate the full typed contract. The present v3 condition would remain a control. Any later proposal should use newly source-checked fictional packets, include both answerable derivation/interpretation tasks and genuinely missing-fact controls, and define common source/numerical/interpretation criteria before generation. Interface-specific structural scores must remain separate. If both conditions fail, the evidence would favor reconsidering the generator's suitability; if a simpler interface succeeds, the interface burden becomes a defensible target for later work. Neither conclusion follows from this campaign alone.

That is a **design recommendation only**. No alternative prompt/schema/model was selected or implemented, no new budget was created, and no inference is authorized by this report. Any future execution would require its own reviewed design and explicit authorization. These already inspected synthetic cases are development checks, not held-out generalization, FinanceBench accuracy, or evidence of downstream OCR performance.

## Audit companion and evidence locators

`SYNTHETIC_V3_VERIFICATION.json` records recomputed hashes, accounting, input/output/timing counts, resource extrema, per-case failure codes and preservation scope. Principal source locators inside the unchanged campaign ZIP are `events/*.json`, `run/run_manifest.json`, `run/authorization/*`, `run/server.stderr.log`, `run/resource-samples/*`, `run/<case>/raw-response.sse`, `raw-content.txt`, `request.json`, `packing.json`, `included-pages.json`, `generic-mechanics.json`, and `case-checks.json`. The operator ZIP contains the console/exit and issuance/pinning logs; the preservation ZIP contains original/final inventories and comparison records.

Review method was deterministic archive hashing and inventory reconciliation, strict re-parsing, frozen-schema/grammar and evaluator replay, Decimal source arithmetic, and AI-assisted source/meaning inspection. No model completion was requested. Attached archives and frozen code/Git identities were checked again after report preparation.
