from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from finocr.schemas import DocumentRecord, TaskRecord


@dataclass(slots=True)
class ManifestAudit:
    document_count: int
    task_count: int
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "document_count": self.document_count,
            "task_count": self.task_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "statistics": self.statistics,
        }


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _resolve_manifest_path(value: str, root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_manifests(
    documents: list[DocumentRecord],
    tasks: list[TaskRecord],
    *,
    require_files: bool = False,
    repository_root: str | Path = ".",
) -> ManifestAudit:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    root = Path(repository_root)

    document_ids = [document.doc_id for document in documents]
    task_ids = [task.task_id for task in tasks]
    duplicate_documents = sorted(
        identifier for identifier, count in Counter(document_ids).items() if count > 1
    )
    duplicate_tasks = sorted(
        identifier for identifier, count in Counter(task_ids).items() if count > 1
    )
    for identifier in duplicate_documents:
        errors.append(_issue("duplicate_doc_id", "Duplicate document id", doc_id=identifier))
    for identifier in duplicate_tasks:
        errors.append(_issue("duplicate_task_id", "Duplicate task id", task_id=identifier))

    by_id = {document.doc_id: document for document in documents}
    for document in documents:
        if not document.doc_id.strip():
            errors.append(_issue("empty_doc_id", "Document id is empty"))
        if document.page_count <= 0:
            errors.append(
                _issue(
                    "invalid_page_count",
                    "Document page count must be positive",
                    doc_id=document.doc_id,
                    page_count=document.page_count,
                )
            )
        if not document.primary_path:
            errors.append(
                _issue(
                    "missing_source_path",
                    "Document has neither source_path nor pdf_path",
                    doc_id=document.doc_id,
                )
            )
        elif require_files:
            source = _resolve_manifest_path(document.primary_path, root)
            if not source.is_file():
                errors.append(
                    _issue(
                        "missing_source_file",
                        "Document source file does not exist",
                        doc_id=document.doc_id,
                        path=document.primary_path,
                    )
                )
        if not document.ocr_input_ready:
            warnings.append(
                _issue(
                    "not_ocr_input_ready",
                    "Document does not point to a verified PDF source",
                    doc_id=document.doc_id,
                    source_format=document.source_format,
                )
            )

    for task in tasks:
        document = by_id.get(task.doc_id)
        if document is None:
            errors.append(
                _issue(
                    "orphan_task",
                    "Task references an unknown document",
                    task_id=task.task_id,
                    doc_id=task.doc_id,
                )
            )
            continue
        if task.task_type == "question_answering" and not (task.question or "").strip():
            errors.append(
                _issue(
                    "empty_question",
                    "Question-answering task has no question",
                    task_id=task.task_id,
                )
            )
        if task.task_type == "question_answering" and not task.answers:
            errors.append(
                _issue(
                    "empty_answers",
                    "Question-answering task has no answers",
                    task_id=task.task_id,
                )
            )
        if len(task.evidence_pages) != len(set(task.evidence_pages)):
            errors.append(
                _issue(
                    "duplicate_evidence_page",
                    "Task repeats an internal evidence page",
                    task_id=task.task_id,
                    evidence_pages=task.evidence_pages,
                )
            )
        invalid_pages = [
            page
            for page in task.evidence_pages
            if isinstance(page, bool)
            or not isinstance(page, int)
            or page < 0
            or page >= document.page_count
        ]
        if invalid_pages:
            errors.append(
                _issue(
                    "invalid_evidence_page",
                    "Task has an evidence page outside the document",
                    task_id=task.task_id,
                    doc_id=task.doc_id,
                    page_count=document.page_count,
                    invalid_pages=invalid_pages,
                )
            )

    statistics = {
        "datasets": dict(sorted(Counter(d.dataset for d in documents).items())),
        "source_formats": dict(
            sorted(Counter(d.source_format or "unspecified" for d in documents).items())
        ),
        "splits": dict(sorted(Counter(d.split for d in documents).items())),
        "task_types": dict(sorted(Counter(t.task_type for t in tasks).items())),
        "question_types": dict(
            sorted(
                Counter(
                    str(t.metadata.get("question_type", "unspecified")) for t in tasks
                ).items()
            )
        ),
        "ocr_ready_documents": sum(document.ocr_input_ready for document in documents),
    }
    return ManifestAudit(
        document_count=len(documents),
        task_count=len(tasks),
        valid=not errors,
        errors=errors,
        warnings=warnings,
        statistics=statistics,
    )

