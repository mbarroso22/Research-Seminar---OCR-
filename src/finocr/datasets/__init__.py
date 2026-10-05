from __future__ import annotations

from pathlib import Path

from finocr.io import read_jsonl
from finocr.schemas import DocumentRecord, TaskRecord

from .finlongdocqa import (
    FinLongDocQAConversion,
    FinLongDocQAError,
    MarkdownReportStore,
    ReportKey,
    audit_finlongdocqa_release,
    convert_finlongdocqa,
    load_finlongdocqa_annotations,
    load_selection,
    split_markdown_pages,
)
from .financebench import (
    FinanceBenchConversion,
    FinanceBenchError,
    convert_financebench,
    select_financebench_pilot,
    write_inventory_csv,
)
from .validation import ManifestAudit, validate_manifests


def load_documents(path: str | Path) -> list[DocumentRecord]:
    return [DocumentRecord.from_dict(value) for value in read_jsonl(path)]


def load_tasks(path: str | Path) -> list[TaskRecord]:
    return [TaskRecord.from_dict(value) for value in read_jsonl(path)]


__all__ = [
    "DocumentRecord",
    "FinLongDocQAConversion",
    "FinLongDocQAError",
    "FinanceBenchConversion",
    "FinanceBenchError",
    "ManifestAudit",
    "MarkdownReportStore",
    "ReportKey",
    "TaskRecord",
    "audit_finlongdocqa_release",
    "convert_finlongdocqa",
    "convert_financebench",
    "load_documents",
    "load_finlongdocqa_annotations",
    "load_selection",
    "load_tasks",
    "select_financebench_pilot",
    "split_markdown_pages",
    "validate_manifests",
    "write_inventory_csv",
]
