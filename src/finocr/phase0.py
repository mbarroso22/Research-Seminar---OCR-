from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from finocr.datasets.finlongdocqa import MarkdownReportStore, ReportKey, split_markdown_pages
from finocr.datasets.validation import ManifestAudit
from finocr.io import iter_jsonl
from finocr.schemas import DocumentRecord, TaskRecord


MANUAL_STATUSES = frozenset({"pass", "concern", "fail"})


def load_manual_checks(path: str | Path) -> list[dict[str, Any]]:
    checks = list(iter_jsonl(path))
    seen: set[str] = set()
    for line_number, check in enumerate(checks, start=1):
        task_id = str(check.get("task_id", "")).strip()
        status = check.get("status")
        if not task_id:
            raise ValueError(f"Manual check line {line_number} has no task_id")
        if task_id in seen:
            raise ValueError(f"Duplicate manual check task_id: {task_id}")
        if status not in MANUAL_STATUSES:
            raise ValueError(
                f"Manual check {task_id} has invalid status {status!r}; "
                f"expected one of {sorted(MANUAL_STATUSES)}"
            )
        if not isinstance(check.get("findings"), list):
            raise ValueError(f"Manual check {task_id} findings must be a list")
        seen.add(task_id)
    return checks


def build_phase0_audit(
    release_audit: dict[str, Any],
    manifest_audit: ManifestAudit,
    documents: list[DocumentRecord],
    tasks: list[TaskRecord],
    manual_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    known_tasks = {task.task_id for task in tasks}
    unknown_checks = sorted(
        str(check["task_id"])
        for check in manual_checks
        if str(check["task_id"]) not in known_tasks
    )
    if unknown_checks:
        raise ValueError(
            "Manual checks reference tasks outside the pilot: " + ", ".join(unknown_checks)
        )

    status_counts = Counter(str(check["status"]) for check in manual_checks)
    human_signoff_pending = sum(
        not bool(check.get("human_signoff", False)) for check in manual_checks
    )
    finding_codes = Counter(
        str(finding.get("code", "unspecified"))
        for check in manual_checks
        for finding in check.get("findings", [])
    )
    source_formats = Counter(document.source_format or "unspecified" for document in documents)
    ocr_ready_count = sum(document.ocr_input_ready for document in documents)
    page_counts = sorted(document.page_count for document in documents)
    years = Counter(str(document.metadata.get("fiscal_year")) for document in documents)
    question_types = Counter(
        str(task.metadata.get("question_type", "unspecified")) for task in tasks
    )

    blockers: list[dict[str, str]] = []
    if not manifest_audit.valid:
        blockers.append(
            {
                "code": "manifest_validation_failed",
                "message": "Unified manifests have structural validation errors.",
            }
        )
    if release_audit.get("released_pdf_count", 0) == 0:
        blockers.append(
            {
                "code": "source_pdfs_unavailable",
                "message": (
                    "The official FinLongDocQA report archive contains Markdown, not the "
                    "source PDFs used to create it."
                ),
            }
        )
    if ocr_ready_count != len(documents):
        blockers.append(
            {
                "code": "pilot_not_ocr_ready",
                "message": (
                    f"Only {ocr_ready_count} of {len(documents)} pilot documents point to "
                    "verified PDF inputs."
                ),
            }
        )
    if status_counts.get("fail", 0):
        blockers.append(
            {
                "code": "manual_ground_truth_failures",
                "message": (
                    f"{status_counts['fail']} of {len(manual_checks)} manually inspected "
                    "tasks have blocking evidence or semantic issues."
                ),
            }
        )
    if human_signoff_pending:
        blockers.append(
            {
                "code": "researcher_signoff_pending",
                "message": (
                    f"{human_signoff_pending} content checks were prepared by assistant "
                    "inspection and still require researcher signoff."
                ),
            }
        )

    return {
        "audit_version": 1,
        "phase": 0,
        "dataset": "FinLongDocQA",
        "source_version": "v1.1",
        "status": "blocked_before_ocr" if blockers else "ready_for_ocr_dry_run",
        "release_integrity": release_audit,
        "pilot": {
            "document_count": len(documents),
            "task_count": len(tasks),
            "years": dict(sorted(years.items())),
            "question_types": dict(sorted(question_types.items())),
            "source_formats": dict(sorted(source_formats.items())),
            "page_count_range": {
                "min": min(page_counts) if page_counts else None,
                "max": max(page_counts) if page_counts else None,
            },
            "internal_page_index_base": 0,
            "source_page_index_base": 1,
            "page_index_conversion": "source_page_number - 1",
            "ocr_ready_document_count": ocr_ready_count,
        },
        "manifest_validation": manifest_audit.to_dict(),
        "manual_review": {
            "sample_size": len(manual_checks),
            "sampling_note": (
                "Purposeful stratified pilot across years, question types, document "
                "lengths, and evidence spans; not a random error-rate estimate."
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "human_signoff_pending": human_signoff_pending,
            "finding_code_counts": dict(sorted(finding_codes.items())),
            "checks": manual_checks,
        },
        "rendering": {
            "requested_dpi": 200,
            "status": "blocked_missing_verified_pdfs" if blockers else "not_started",
            "markdown_evidence_packets_are_pdf_renders": False,
        },
        "ocr_readiness": {
            "ready": not blockers,
            "blockers": blockers,
        },
        "next_actions": [
            "Acquire the exact source PDFs used by the dataset authors or obtain an author-supplied PDF-to-report mapping.",
            "Verify PDF page counts and page labels against every selected Markdown '# Page N' marker.",
            "Resolve, correct, or exclude tasks marked fail or concern in the manual-review file.",
            "Have the researcher inspect the evidence packets and record human signoff.",
            "Populate pdf_path only after identity and pagination checks pass.",
            "Render verified evidence pages at 200 DPI, then rerun the audit.",
            "Install no OCR model until all Phase 0 blockers are cleared.",
        ],
    }


def phase0_audit_markdown(audit: dict[str, Any]) -> str:
    release = audit["release_integrity"]
    pilot = audit["pilot"]
    validation = audit["manifest_validation"]
    manual = audit["manual_review"]
    lines = [
        "# FinLongDocQA Phase 0 data-quality audit",
        "",
        f"**Status:** `{audit['status']}`",
        "",
        "## Outcome",
        "",
        (
            "The unified pilot manifests are structurally valid, but the pilot is not "
            "ready for OCR. The official release supplies page-delimited Markdown rather "
            "than the source PDFs, and the content-level review found ground-truth issues "
            "that structural checks cannot detect."
        ),
        "",
        "## Official v1.1 release audit",
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| QA records | {release['annotation_count']:,} |",
        f"| Markdown reports | {release['report_count']:,} |",
        f"| Companies | {release['company_count']:,} |",
        f"| Reports referenced by QA | {release['task_document_count']:,} |",
        f"| Reports without QA | {release['reports_without_tasks_count']:,} |",
        f"| Missing report mappings | {len(release['missing_reports']):,} |",
        f"| Out-of-range evidence references | {len(release['invalid_evidence_references']):,} |",
        f"| Released PDFs | {release['released_pdf_count']:,} |",
        "",
        (
            "All report page markers are contiguous and one-based. The adapter converts "
            "evidence pages once to zero-based internal indices and retains the source "
            "values in task metadata. Reference Python programs were preserved but never "
            "executed by the adapter."
        ),
        "",
        "## Ten-report pilot",
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| Documents | {pilot['document_count']} |",
        f"| Tasks | {pilot['task_count']} |",
        f"| Page-count range | {pilot['page_count_range']['min']}–{pilot['page_count_range']['max']} |",
        f"| Manifest errors | {len(validation['errors'])} |",
        f"| OCR-ready PDFs | {pilot['ocr_ready_document_count']} |",
        "",
        "Question types: "
        + ", ".join(f"`{key}` {value}" for key, value in pilot["question_types"].items())
        + ".",
        "",
        "## Manual content review",
        "",
        (
            "The ten checks were purposefully stratified, so these counts diagnose the "
            "pilot and are not a random estimate of the full dataset's error rate."
        ),
        "",
        "| Source task | Company/year | Status | Main finding |",
        "|---:|---|---|---|",
    ]
    for check in manual["checks"]:
        summary = str(check.get("summary", "")).replace("|", "\\|")
        lines.append(
            f"| {check.get('source_task_id')} | {check.get('company')}/{check.get('year')} "
            f"| `{check['status']}` | {summary} |"
        )
    lines.extend(
        [
            "",
            "## OCR and rendering gate",
            "",
            "Rendering at 200 DPI was not performed because there are no verified source "
            "PDFs in the official release. Rendering Markdown into synthetic PDFs would "
            "change the input distribution and would not test OCR on the documents used to "
            "create the benchmark.",
            "",
            "Blocking items:",
            "",
        ]
    )
    for blocker in audit["ocr_readiness"]["blockers"]:
        lines.append(f"- `{blocker['code']}` — {blocker['message']}")
    lines.extend(["", "## Next action", ""])
    for index, action in enumerate(audit["next_actions"], start=1):
        lines.append(f"{index}. {action}")
    return "\n".join(lines) + "\n"


def write_evidence_packets(
    reports_source: str | Path,
    tasks: list[TaskRecord],
    manual_checks: list[dict[str, Any]],
    output_dir: str | Path,
) -> list[Path]:
    """Write text evidence packets for review; these are explicitly not PDF renders."""

    by_task = {task.task_id: task for task in tasks}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with MarkdownReportStore(reports_source) as reports:
        page_cache: dict[ReportKey, dict[int, str]] = {}
        for check in manual_checks:
            task = by_task[str(check["task_id"])]
            key = ReportKey(str(check["company"]), str(check["year"]))
            pages = page_cache.setdefault(
                key,
                split_markdown_pages(
                    reports.read_text(key), source=f"{key.company}/{key.year}.md"
                ),
            )
            source_pages = list(task.metadata["source_page_numbers"])
            lines = [
                f"# Evidence packet: source task {check['source_task_id']}",
                "",
                "> This is extracted text from the released Markdown, not a rendered PDF.",
                "",
                f"- Document: `{key.company}/{key.year}`",
                f"- Unified task: `{task.task_id}`",
                f"- Review status: `{check['status']}`",
                f"- Source pages (one-based): `{source_pages}`",
                f"- Internal pages (zero-based): `{task.evidence_pages}`",
                f"- Question: {task.question}",
                f"- Gold answer: `{task.answers[0]}`",
                "",
            ]
            for page_number in source_pages:
                lines.extend(
                    [
                        f"## Source Page {page_number}",
                        "",
                        pages[page_number],
                        "",
                    ]
                )
            target = output / f"task_{check['source_task_id']}.md"
            target.write_text("\n".join(lines), encoding="utf-8")
            written.append(target)
    return written
