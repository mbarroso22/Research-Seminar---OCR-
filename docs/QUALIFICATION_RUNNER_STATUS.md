# Qualification implementation status

Historical runner-v1 record. The current offline binding increment and its
pending Windows checks are described in [QUALIFICATION_BINDING_STATUS.md](QUALIFICATION_BINDING_STATUS.md).
The validation/results below describe the predecessor implementation.

Implemented and offline-tested on 2026-10-19. This increment applies over the
completed preparation + validation-v2 + review-docs + offline-repair edits.
Its exact base tree is `2a6bc022ec20bae751bb54e85b9be9c473cc093e`.
The offline-repair prerequisite patch SHA-256 is
`598ccbced5a1d4d2b85de110a1245e2a7f6a69dae965156b3ee82c0c26d267f1`.
Use [the staged Windows guide](QUALIFICATION_RUNNER_WINDOWS.md).

## Implemented, with inference still paused

The new sibling `finocr_qualification` package implements the prospectively
specified v3 lifecycle. Existing `finocr_answer` files, including its contract,
evaluator, historical audit and unconditional pause, remain byte-identical.
All existing scripts, baseline/OCR source, control/config/dependency files,
README and historical result files remain unchanged. The plan and a checksum-
anchored frozen reference are added; the latter includes historical raw-tree
hashes, baseline/control source identities and exact prompt/token/grammar controls.

- Public `run_qualification.py` stops at the unchanged unconditional pause before
  reading a preparation file, opening a ledger or starting a process. No enable
  flag, environment override, budget issuer or ticket issuer exists. Its internal
  lifecycle also requires a separately bound authorization reference, which the
  public path does not supply in this revision.
- Offline preparation is explicitly not authorization. It checks existing assets,
  runtime/packages, both exhausted historical campaigns, baseline/control and
  contract bytes, source-checked rubric/plan, all six tokenizer controls, native
  effective grammar and hardware/resource prerequisites. It creates only a new
  offline report and schema file outside protected/code/asset/campaign paths.
- The execution lifecycle has one fixed future anchor, exclusive creation, no
  resume/restart API, hash-chained append-only event files, flush/fsync before
  completion submission and conservative charging of uncertain attempts. A torn
  record or failed fsync stops submission and blocks reuse of that anchor.
  Charged attempts, submission attempts and received responses are reported
  separately; conservative charging does not claim successful model execution.
  Directory syncing is used where available; Python's Windows directory-fsync
  limitation is explicit. This is not a hardware/power-loss durability guarantee.
- All six nongenerating backend template/token controls precede any completion.
  Actual launch/device/offload/FA/KV/context/decoder settings stay fixed. Scoped
  transient caches are confined to the new campaign only after later authorization.
  The model, quantization, backend and existing caches are never replaced.
- The owned server has startup and total-request deadlines, live resource guards,
  RAM/GPU brackets and threshold enforcement. Failed monitoring/resource checks
  stop the owned process. Other machine runs/processes are never controlled.
- Invalid JSON/schema/grammar, transport/cancellation/timeout, truncated/limited
  output, identity/runtime/preservation failures are terminal. Schema-valid genuine
  numerical, citation and support-mechanics errors remain failures; the fixed
  remaining cases may run only to record the predeclared profile. No repairs,
  retries, adaptive prompts or output selection are implemented.
- Each attempt retains the exact ordered request, canonical identity, packed
  prompt/tokens/pages/source hashes, raw/partial SSE and content, backend terminal
  record, generic mechanics and unchanged case-specific diagnostics. Separate
  axes expose contract, numerical components/arithmetic, literal versus semantic
  support, interpretation and resource evidence. No mechanical pass is promoted
  to fully supported correctness.
- Both human reviews and adjudication remain pending. The exporter includes every
  available evidence file and manual record, verifies content hashes and ZIP CRC,
  and emits an external checksum sidecar. It refuses overwrite/nested paths and
  detects source mutation during export. Manual reviews can be added as separate
  files and exported offline into a new archive, without editing raw outputs.

The standalone C++ probe uses only the pinned b6500 schema converter and a small
wrapper. It initializes no vocabulary, model, sampler, GPU or server. An existing
compiler is required; the guide installs nothing. If Windows has no supported
compiler, the native/Windows preparation gate stays pending. Do not bypass it.

## Completed validation versus pending execution

| Check | Status |
|---|---|
| New qualification tests | 45 pass, mocked transports/processes only |
| Complete regression suite | 295 pass, no skips (includes the prior 250) |
| Actual standalone native converter on development host | Builds with existing g++; native and Python converters agree on all 18,525 frozen grammar bytes |
| Frozen identities | Contract, instruction, six prompt/token controls, grammar, evaluator, 46 baseline Python files and expansion-v1 control unchanged |
| Preservation | Original runs, ledgers, old patch/recovery artifacts and existing environments/caches are not mutated by this increment |
| Windows PowerShell/native build/preparation/runtime-resource checks | Pending local execution; no claim of a completed Windows check in this increment |
| Real generation, runtime qualification, human source/interpretation scoring | Not executed; no new experimental results |

Failure tests cover durable charge before mocked submission; interrupted, duplicate
and exhausted ledgers; fsync failures; immutable raw/partial outputs; real helper
serialization and parent deadlines under mocked HTTP; FA/runtime/offload drift;
resource thresholds/stale samples; all-six preflight; strict invalid-output stop;
numerical/operand failures; history additions/deletions; altered report bindings;
export integrity; and the genuine unchanged public pause.

The old source fingerprint still describes the repaired offline contract.
The new runner records its own actual per-file source fingerprint plus HEAD and
dirty state; it never assigns the old hash to the new implementation or reseals
an old setup. Changing code or committing after offline preparation invalidates
that binding, requiring a new offline review, not an execution retry.

The historical v2 result stays **1/6 mechanically passing**. Total real requests
spent stay **12** and currently authorized remaining stay **0**. Mock-fixture
charges and handwritten responses are test evidence, not a new allowance or model
result. The six inspected synthetic cases remain development checks; no
generalization or FinanceBench-accuracy claim follows. Expansion v1 at k=5 and
the native/CPU-OCR/GPU-OCR pilot are preserved. No FinanceBench answers are generated.
