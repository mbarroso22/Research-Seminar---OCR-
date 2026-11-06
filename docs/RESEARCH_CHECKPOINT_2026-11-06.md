# OCR Research Seminar — resume handoff

Saved 6 November 2026 (Eastern). This is the latest status note for this chat. Earlier handoffs are historical and contain stages that have since completed. API setup is paused at the user's request.

## Repository and branches

Repository: https://github.com/mbarroso22/Research-Seminar---OCR-.git

Last reported Windows working trees:

| Checkout | Branch | Recorded HEAD | Role |
|---|---|---|---|
| C:\Users\mbarroso\Downloads\Research-Seminar-OCR-review | answer-feasibility-results | 6531786ce8bea04ac82c89517a0806b7faf8bfe1 | Processing/research checkout, with later local broader/runtime/hybrid/larger-study changes |
| C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current | main | 61a696d9ca7dd0c505b1de662ca3eaea57ed3e9d | Original worktree |

Other recorded branches/checkpoints: native-ocr-pilot-results at 828ba06; gpu-ocr-validation at 3d0fc59. The former was listed as a local branch and origin-tracking ref; the latter was historically recorded as an origin-tracking ref. Do not assume either is the active checkout or that these are current remote tips.

The latest Windows snapshot supplied by the user showed review on answer-feasibility-results at 6531786, tracking origin/answer-feasibility-results. That snapshot is not a fresh inspection today. No later commit, push, merge or new branch has been verified. Delivered and executed local changes are not automatically included in that commit.

Preserve modified cli.py, native_baseline.py, ocr_comparison.py and stopword_comparison.py, plus added broader preparation/tests, hybrid pipeline/semantic retrieval/policy/lock/tests, and larger-study implementation. Do not reset, clean, overwrite, reapply patches or checkout over local work.

If resuming Git work, first collect this read-only snapshot in PowerShell:

```powershell
$Repo = 'C:\Users\mbarroso\Downloads\Research-Seminar-OCR-review'
git -C $Repo remote -v
git -C $Repo status --short --branch
git -C $Repo log -5 --oneline
git -C $Repo branch -vv
git -C $Repo worktree list
git -C $Repo diff --stat
git -C $Repo diff --cached --stat
```

These commands do not fetch, commit, push or back up untracked file contents. Review the current files before proposing a research checkpoint commit. Keep model weights, source PDFs, environments and large run payloads outside Git. Never commit API secrets.

## Storage and reproducibility

Windows data root: C:\Users\mbarroso\financial-ocr-data

Code/history live in Git; experiment caches, assets, environments and run folders live under the data root; review ZIPs preserve selected reproducibility evidence; advisor documents and chat deliverables have also been saved. A review ZIP is not a full-machine backup. No fresh Windows or Google Drive backup verification has been performed in this pause.

FinanceBench source identities:
- financebench_open_source.jsonl: b927dae968f6f8dd36a920393717d0a5c2a537d0c6bc93a7e754bf356d7a73b0
- financebench_document_information.jsonl: c9bee8f606e1abbac90392e0c05debfc2f2821022cd09298f1230d825e129e7b

Sources remain under raw\financebench\data and raw\financebench\pdfs. Preserve original bytes, page indices, frozen questions and separate reference annotations.

## Verified completed work

1. Historical six-company native/GPU-OCR comparison completed on 6531786 plus local changes: nine reports, 1,351 pages, 24 questions. Do not repeat it or call it untouched confirmation data.
2. Original fixed hybrid development experiment was actually applied, installed and executed on Windows, with 219 passing tests. Twelve documents, 2,620 pages, 24 questions. The fixed gate FAILED: neither native nor OCR hybrid completed a multi-page item in the top five. This supersedes the older handoff's 'Windows execution unconfirmed' state.
3. Larger exploratory study completed: 20 companies, 43 reports, 7,003 pages, 58 questions, including 22 multi-page items. Setup passed 239 tests. Native extraction and GPU OCR completed, followed by fixed BM25, semantic and hybrid retrieval. Completion/preservation/export checks passed. This study had no promotion gate; the original pilot FAIL remains unchanged.

| Text | Method | Recall@5 | Complete@5 | Multi-page complete@5 |
|---|---|---:|---:|---:|
| Native | BM25 | 25.862069% | 13/58 | 1/22 |
| Native | Semantic | 55.172414% | 28/58 | 9/22 |
| Native | Hybrid | 46.551724% | 22/58 | 2/22 |
| OCR | BM25 | 25.862069% | 13/58 | 1/22 |
| OCR | Semantic | 55.172414% | 27/58 | 7/22 |
| OCR | Hybrid | 46.551724% | 22/58 | 2/22 |

Primary OCR minus native BM25 Recall@5 = 0 points, company-cluster bootstrap interval [0,0]. Retrieval recall is not answer accuracy. Costs are single-run descriptive measurements, not controlled speedup or energy findings.

## Qwen answer-generation phase

Saved text-only Qwen3-4B-Instruct-2507, quantized Q4_K_M; no project fine-tuning or distillation performed. Model SHA-256: 80f7dccce5ae984d2b40ba998871288e367fcb76a759f89c55e7139e4632f0e1. Revision cdbee75f17c01a7cc42f958dc650907174af0554. llama.cpp b6500/a7a98e0f, Vulkan on Windows, RTX 3070 Ti 8 GB. Runs used context 16,384, output cap 1,024, temperature 0, seed 0, no context shifting. Official configuration's 262,144 maximum positions does not establish that this context fits the GPU.

Assets: data root\answer-generation\qwen3-4b-instruct-2507-v1\assets. Backend contains llama-cli.exe, llama-server.exe and llama-tokenize.exe. Converted model: assets\converted\model-Q4_K_M.gguf. Preserve associated official configuration, tooling and audits.

Completed:
- Counted full-report and semantic-top-five prompt tokens for all 58 questions without inference. Full-report prompts: min 52,804, median 129,544, max 555,870. Retrieved five-page prompts: min 2,904, median 4,600.5, max 10,308. All retrieved prompts fit 16,384 with 1,024 reserved output; no full reports fit. These counts use Qwen's tokenizer.
- One largest-retrieved-prompt feasibility request completed in about 27.5 seconds. This established execution feasibility, not benchmark-wide accuracy.
- Six selected development questions ran in paired retrieved/oracle conditions: 12 requests, all processes completed, inputs unchanged. Oracle uses native text from annotated pages, without reference answers or justifications. Total saved Qwen prompt tokens = 38,183; maximum combined generated allowance = 12,288.
- Reviewed all 12 outputs against user-provided reference records and checked five original-page images. Final answer-level DEVELOPMENT score: retrieved 3/6, oracle 4/6. Retrospective rubric, not held-out confirmation or official benchmark accuracy.

| Task suffix | Retrieved | Oracle | Key finding |
|---|---|---|---|
| 01148 | Fail | Pass | Amcor industry: retrieved output empty despite relevant page present |
| 07966 | Pass | Pass | Activision three-year capex/revenue = 1.9% |
| 02981 | Pass | Pass | Corning three-year operating margin = 10.3%; oracle intermediate notation error retained |
| 00790 | Fail | Fail | CVS: No versus reference Yes; physical-assets interpretation ambiguity flagged |
| 03882 | Pass | Pass | Amcor net receivables = $1,615.9 million, confirmed source precision versus rounded reference |
| 00070 | Fail | Fail | American Water Works: oracle gets −$1,561 million but contradicts itself with opening Yes/positive |

Source review confirmed AWW current assets 1,250 and current liabilities 2,811, millions. Reference answer is supported but its supplied justification expression equals +124 and is inconsistent. Preserve original reference; retain separate adjudication. CVS source figures reproduce the reference ratios but do not eliminate interpretive ambiguity. Only the five exported Amcor 2020, CVS 2022 and AWW 2022 pages were visually inspected in this source review. Other cases used saved text, references and arithmetic checks.

See Qwen_Development_Scorecard_2026-11-06.md for complete scoring rules and limitations.

## Current research specification and planned work

Working question: Can a local financial-document assistant using selected evidence approach a stronger model's answer quality while reducing context processing and deployment resources? Acceptable accuracy-loss threshold remains to be agreed before confirmatory evaluation. Existing inspected sets are exploratory/development data.

Immediate next experiment: one stronger hosted model on the exact same six questions and two evidence conditions (12 requests), preserving instructions, page text and ordering, adapting only chat serialization. Freeze rubric before reading new outputs. Record exact model/version, settings, billed input/output/reasoning tokens, finish reasons, latency and actual charges. Do not send reference labels into inference. Review identities blinded where possible. Provider token counts differ from Qwen counts.

Only after this comparison, choose a targeted improvement: evidence selection/context expansion, source-grounded abbreviation memory, response consistency, or table/chart interpretation. A persistent document index or memory store is different from an LLM's attention KV cache. No memory feature has been implemented or validated in this phase.

Full-document generation has NOT been executed. Another local model, earnings-call dataset collection/ground-truth creation, visual parser/annotation, Unlimited-OCR integration and split-model processing have NOT been executed. Unlimited-OCR was researched as a parser candidate; chart image references are not proof of chart understanding. Qwen here is text-only. Use targeted vision experiments with original page/region references before claiming visual gains.

## OpenAI API setup — paused

User asked about costs, then began account/project setup. Current recommendation was GPT-6.1 Sol as a hosted reference, with a fixed small request/output budget. Pricing estimates were preliminary; recheck official model prices before execution. Suggested project name OCR Research Seminar and key name Windows research comparison. Suggested spend limit $2/month; this was advice, not a verified configured cap.

User supplied a project Limits screenshot/table. It showed gpt-6.1-sol at 10,000 TPM and 3 RPM, alongside other models. This proves the displayed rate-limit configuration only, not usable credits, successful authentication, model access or a dollar cap. Spend controls were not visible on that screenshot. User was directed to Organization settings → Billing and spending controls; no completed action returned.

NOT VERIFIED: API key creation, key storage, funded billing, usable credits, spend alerts/hard limit, automatic recharge setting, API authentication or any inference request. No key has been shared here. No OpenAI API experiment, SDK installation or API runner implementation was performed in this phase. Do not describe setup as complete or infer that rates are payment authorization.

Resume by asking whether the key was created and what nonsecret billing status shows. Keep the key private, outside source code, chat, screenshots, exports and Git. Load securely on Windows. Check access, provider token estimates and bounded run cost before the comparison. The user has now paused setup; do not launch requests, purchase credits or start experiments while saving.

## Important run locations and archive identities

Larger run stamp: larger-exploratory-20261105T222841Z-03722185.
Windows: audits\STAMP; derived\native\STAMP; derived\retrieval\STAMP; derived\ocr\larger-exploratory-gpu-200dpi-20261105T222841Z-03722185. Keep source native_pages.jsonl, raw OCR attempts, images, rankings, vectors, frozen cohort, costs and run manifests.

| Archive | SHA-256 |
|---|---|
| hybrid-development-20261105T200123Z-658f5e56-review.zip | 4fc45ced86de24b3ba4795b0ca20b0eb4c5101d13bed1da90e67e2cd46371b78 |
| larger-exploratory-20261105T222841Z-03722185-review.zip | 7ad86e7cfa31decf138b9a20b48685dc766d1f0e7a5e314be603ff0ccdb723c0 |
| qwen-context-counts-20261106T181439Z-8b2d3d8f.zip | cf6ebce08af422c0bca4aba6cd02d05c8018d9c89f5b00a2455693c3867c76f1 |
| qwen-retrieved-feasibility-20261106T181944Z-79a42f2c.zip | 45dbf67c312002be0453cbcea579b25509b2c0a23f77b55b004923cdb760a386 |
| qwen-dev-six-20261106T182431Z-f3a5c68e.zip | c69e0e73e89d0f6bf11d19f3753ae7e2cc44bd18639f241bb0b6eaf0ddd2eb7c |
| qwen-source-review-20261106T203105Z-151841cc.zip | 81570eb14017d771d3d48e23d58403c91f54cb98e167d9097870a28121ef7e86 |

New pause bundle contains this handoff, the current scorecard, advisor DOCX documents, prior progress/audit notes (clearly historical), delivered Qwen scripts and the four small Qwen review archives. SHA256SUMS.json lists every included payload. It deliberately references the already-preserved larger archives rather than duplicating all raw processing data. This bundle is not a fresh export of the Windows dirty working tree or a Git commit.

Resume instruction: Read this handoff and the scorecard first. Continue from API setup only when the user is ready. Do not rerun completed OCR, embeddings, retrieval, token counts or Qwen development requests. Collect fresh read-only Git state before any code checkpoint operation.
