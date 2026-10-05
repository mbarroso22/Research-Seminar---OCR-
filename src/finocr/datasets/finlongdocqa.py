from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from finocr.io import iter_jsonl, read_json
from finocr.schemas import DocumentRecord, TaskRecord


DATASET_ID = "finlongdocqa"
OFFICIAL_REPOSITORY = (
    "https://github.com/AI-Application-and-Integration-Lab/FinLongDocQA"
)
OFFICIAL_DATASET = "https://huggingface.co/datasets/Amian/FinLongDocQA"
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "company",
        "year",
        "question",
        "type",
        "thoughts",
        "page_numbers",
        "python_code",
        "answer",
    }
)
QUESTION_TYPES = frozenset({"mixed", "table", "text"})
PAGE_HEADING = re.compile(r"^# Page ([1-9]\d*)\s*$", re.MULTILINE)
ARCHIVE_MEMBER = re.compile(r"^reports/([^/]+)/(\d{4})\.md$")
YEAR = re.compile(r"^\d{4}$")


class FinLongDocQAError(ValueError):
    """Raised when the upstream release violates the expected data contract."""


@dataclass(frozen=True, order=True, slots=True)
class ReportKey:
    company: str
    year: str

    def __post_init__(self) -> None:
        if not self.company or "/" in self.company or "\\" in self.company:
            raise FinLongDocQAError(f"Unsafe or empty company value: {self.company!r}")
        if not YEAR.fullmatch(self.year):
            raise FinLongDocQAError(f"Expected four-digit year, got {self.year!r}")

    @property
    def doc_id(self) -> str:
        return f"{DATASET_ID}:{self.company}:{self.year}"

    @property
    def archive_member(self) -> str:
        return f"reports/{self.company}/{self.year}.md"

    def to_dict(self) -> dict[str, str]:
        return {"company": self.company, "year": self.year}


@dataclass(slots=True)
class FinLongDocQAConversion:
    documents: list[DocumentRecord]
    tasks: list[TaskRecord]
    selected_keys: list[ReportKey]
    raw_records: list[dict[str, Any]]


def _normalize_annotation(raw: dict[str, Any], line_number: int) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - raw.keys())
    if missing:
        raise FinLongDocQAError(
            f"Annotation line {line_number} is missing fields: {', '.join(missing)}"
        )

    task_id = str(raw["id"]).strip()
    company = str(raw["company"]).strip()
    year = str(raw["year"]).strip()
    ReportKey(company, year)
    question = raw["question"]
    question_type = raw["type"]
    page_numbers = raw["page_numbers"]
    answer = raw["answer"]

    if not task_id:
        raise FinLongDocQAError(f"Annotation line {line_number} has an empty id")
    if not isinstance(question, str) or not question.strip():
        raise FinLongDocQAError(f"Annotation {task_id} has an empty question")
    if question_type not in QUESTION_TYPES:
        raise FinLongDocQAError(
            f"Annotation {task_id} has unsupported type {question_type!r}"
        )
    if not isinstance(raw["thoughts"], str):
        raise FinLongDocQAError(f"Annotation {task_id} thoughts must be a string")
    if not isinstance(raw["python_code"], str):
        raise FinLongDocQAError(f"Annotation {task_id} python_code must be a string")
    if not isinstance(page_numbers, list) or not page_numbers:
        raise FinLongDocQAError(
            f"Annotation {task_id} page_numbers must be a non-empty list"
        )
    if any(isinstance(page, bool) or not isinstance(page, int) for page in page_numbers):
        raise FinLongDocQAError(
            f"Annotation {task_id} page_numbers must contain integers"
        )
    if any(page < 1 for page in page_numbers):
        raise FinLongDocQAError(
            f"Annotation {task_id} has a source page below one: {page_numbers}"
        )
    if len(page_numbers) != len(set(page_numbers)):
        raise FinLongDocQAError(
            f"Annotation {task_id} repeats an evidence page: {page_numbers}"
        )
    if isinstance(answer, bool) or not isinstance(answer, Real):
        raise FinLongDocQAError(f"Annotation {task_id} answer is not numeric")
    if not math.isfinite(float(answer)):
        raise FinLongDocQAError(f"Annotation {task_id} answer is not finite")

    normalized = dict(raw)
    normalized.update(
        {
            "id": task_id,
            "company": company,
            "year": year,
            "question": question.strip(),
            "type": question_type,
            "page_numbers": list(page_numbers),
        }
    )
    return normalized


def load_finlongdocqa_annotations(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw in enumerate(iter_jsonl(path), start=1):
        record = _normalize_annotation(raw, line_number)
        if record["id"] in seen_ids:
            raise FinLongDocQAError(f"Duplicate annotation id: {record['id']}")
        seen_ids.add(record["id"])
        records.append(record)
    if not records:
        raise FinLongDocQAError(f"No annotations found in {path}")
    return records


def load_selection(path: str | Path) -> tuple[list[ReportKey], dict[ReportKey, dict[str, Any]]]:
    value = read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("documents"), list):
        raise FinLongDocQAError("Selection must be an object with a documents list")

    keys: list[ReportKey] = []
    metadata: dict[ReportKey, dict[str, Any]] = {}
    for index, item in enumerate(value["documents"], start=1):
        if not isinstance(item, dict):
            raise FinLongDocQAError(f"Selection item {index} must be an object")
        key = ReportKey(str(item.get("company", "")).strip(), str(item.get("year", "")).strip())
        if key in metadata:
            raise FinLongDocQAError(f"Duplicate selected report: {key.company}/{key.year}")
        keys.append(key)
        metadata[key] = {k: v for k, v in item.items() if k not in {"company", "year"}}
    if not keys:
        raise FinLongDocQAError("Selection contains no documents")
    return keys, metadata


class MarkdownReportStore:
    """Read official page-delimited reports from reports.zip or an extracted directory."""

    def __init__(self, source: str | Path):
        self.source = Path(source)
        self._zip: zipfile.ZipFile | None = None
        self._members: dict[ReportKey, str | Path] = {}

    def __enter__(self) -> "MarkdownReportStore":
        if self.source.is_file() and self.source.suffix.lower() == ".zip":
            self._zip = zipfile.ZipFile(self.source)
            for member in self._zip.namelist():
                match = ARCHIVE_MEMBER.fullmatch(member)
                if not match:
                    continue
                key = ReportKey(*match.groups())
                if key in self._members:
                    raise FinLongDocQAError(
                        f"Archive contains duplicate report key {key.company}/{key.year}"
                    )
                self._members[key] = member
        elif self.source.is_dir():
            base = self.source / "reports" if (self.source / "reports").is_dir() else self.source
            for report in sorted(base.glob("*/*.md")):
                relative = report.relative_to(base)
                if len(relative.parts) != 2:
                    continue
                key = ReportKey(relative.parts[0], report.stem)
                if key in self._members:
                    raise FinLongDocQAError(
                        f"Directory contains duplicate report key {key.company}/{key.year}"
                    )
                self._members[key] = report
        else:
            raise FinLongDocQAError(
                f"Reports source must be a .zip file or directory: {self.source}"
            )

        if not self._members:
            raise FinLongDocQAError(f"No reports/<company>/<year>.md files in {self.source}")
        return self

    def __exit__(self, *_: object) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None

    def keys(self) -> list[ReportKey]:
        return sorted(self._members)

    def contains(self, key: ReportKey) -> bool:
        return key in self._members

    def read_bytes(self, key: ReportKey) -> bytes:
        try:
            member = self._members[key]
        except KeyError as exc:
            raise FinLongDocQAError(
                f"Missing report for {key.company}/{key.year}"
            ) from exc
        if self._zip is not None:
            return self._zip.read(str(member))
        return Path(member).read_bytes()

    def read_text(self, key: ReportKey) -> str:
        return self.read_bytes(key).decode("utf-8-sig")

    def materialize(self, key: ReportKey, destination_root: str | Path) -> Path:
        target = Path(destination_root) / key.company / f"{key.year}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        member = self._members[key]
        if self._zip is None and Path(member).resolve() == target.resolve():
            return target
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(self.read_bytes(key))
        temporary.replace(target)
        return target


def split_markdown_pages(text: str, *, source: str = "report") -> dict[int, str]:
    matches = list(PAGE_HEADING.finditer(text))
    if not matches:
        raise FinLongDocQAError(f"{source} has no '# Page N' markers")

    pages: dict[int, str] = {}
    order: list[int] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        if page_number in pages:
            raise FinLongDocQAError(f"{source} repeats page marker {page_number}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages[page_number] = text[match.end() : end].strip()
        order.append(page_number)

    expected = list(range(1, max(order) + 1))
    if order != expected:
        raise FinLongDocQAError(
            f"{source} page markers are not contiguous and ordered: "
            f"first={order[:5]}, last={order[-5:]}"
        )
    return pages


def _portable_path(path: Path, repository_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _answer_text(answer: int | float) -> str:
    return json.dumps(answer, ensure_ascii=False, allow_nan=False)


def _task_sort_key(task: TaskRecord) -> tuple[int, int | str]:
    source_id = str(task.metadata["source_task_id"])
    return (0, int(source_id)) if source_id.isdigit() else (1, source_id)


def convert_finlongdocqa(
    annotations_path: str | Path,
    reports_source: str | Path,
    selected_keys: list[ReportKey],
    materialize_root: str | Path,
    repository_root: str | Path,
    *,
    source_version: str = "v1.1",
    selection_metadata: dict[ReportKey, dict[str, Any]] | None = None,
) -> FinLongDocQAConversion:
    """Convert selected FinLongDocQA reports to unified manifests.

    The official release uses one-based page labels. This is the only function
    that changes the page base: unified evidence pages are zero-based, while
    original values are retained in task metadata.
    """

    records = load_finlongdocqa_annotations(annotations_path)
    selected = list(dict.fromkeys(selected_keys))
    selected_set = set(selected)
    selection_metadata = selection_metadata or {}
    rows_by_key: dict[ReportKey, list[dict[str, Any]]] = {key: [] for key in selected}
    for record in records:
        key = ReportKey(record["company"], record["year"])
        if key in selected_set:
            rows_by_key[key].append(record)

    without_tasks = [key for key, rows in rows_by_key.items() if not rows]
    if without_tasks:
        labels = ", ".join(f"{key.company}/{key.year}" for key in without_tasks)
        raise FinLongDocQAError(f"Selected reports have no annotations: {labels}")

    root = Path(repository_root)
    documents: list[DocumentRecord] = []
    tasks: list[TaskRecord] = []
    with MarkdownReportStore(reports_source) as reports:
        missing = [key for key in selected if not reports.contains(key)]
        if missing:
            labels = ", ".join(f"{key.company}/{key.year}" for key in missing)
            raise FinLongDocQAError(f"Selected reports are missing: {labels}")

        for key in sorted(selected):
            pages = split_markdown_pages(
                reports.read_text(key), source=f"{key.company}/{key.year}.md"
            )
            page_count = len(pages)
            report_path = reports.materialize(key, materialize_root)
            document = DocumentRecord(
                doc_id=key.doc_id,
                dataset=DATASET_ID,
                pdf_path=None,
                split="test",
                page_count=page_count,
                source_path=_portable_path(report_path, root),
                source_format="markdown",
                metadata={
                    "company": key.company,
                    "fiscal_year": key.year,
                    "source_version": source_version,
                    "source_page_index_base": 1,
                    "internal_page_index_base": 0,
                    "page_marker_pattern": "# Page N",
                    "released_source_kind": "page-delimited Markdown generated with MinerU",
                    "official_repository": OFFICIAL_REPOSITORY,
                    "official_dataset": OFFICIAL_DATASET,
                    "ocr_input_ready": False,
                    "source_pdf_status": "not_in_official_release",
                    "selection": selection_metadata.get(key, {}),
                },
            )
            documents.append(document)

            for record in rows_by_key[key]:
                source_pages = record["page_numbers"]
                invalid = [page for page in source_pages if page > page_count]
                if invalid:
                    raise FinLongDocQAError(
                        f"Task {record['id']} cites pages {invalid} beyond "
                        f"{key.company}/{key.year}'s {page_count} pages"
                    )
                tasks.append(
                    TaskRecord(
                        task_id=f"{DATASET_ID}:{record['id']}",
                        doc_id=key.doc_id,
                        task_type="question_answering",
                        question=record["question"],
                        answers=[_answer_text(record["answer"])],
                        evidence_pages=[page - 1 for page in source_pages],
                        metadata={
                            "source_task_id": record["id"],
                            "source_version": source_version,
                            "question_type": record["type"],
                            "source_page_numbers": source_pages,
                            "source_page_index_base": 1,
                            "internal_page_index_base": 0,
                            "page_index_conversion": "source_page_number - 1",
                            "answer_numeric": record["answer"],
                            "reference_reasoning": record["thoughts"],
                            "reference_program": record["python_code"],
                            "reference_program_executed_by_adapter": False,
                        },
                    )
                )

    documents.sort(key=lambda item: item.doc_id)
    tasks.sort(key=_task_sort_key)
    selected_raw_records = [
        record
        for record in records
        if ReportKey(record["company"], record["year"]) in selected_set
    ]
    return FinLongDocQAConversion(
        documents, tasks, sorted(selected), selected_raw_records
    )


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_finlongdocqa_release(
    annotations_path: str | Path,
    reports_source: str | Path,
) -> dict[str, Any]:
    """Run release-wide structural checks without executing reference programs."""

    annotations_file = Path(annotations_path)
    reports_file = Path(reports_source)
    records = load_finlongdocqa_annotations(annotations_file)
    task_keys = {ReportKey(row["company"], row["year"]) for row in records}
    type_counts = Counter(row["type"] for row in records)
    year_counts = Counter(row["year"] for row in records)
    evidence_cardinality = Counter(len(row["page_numbers"]) for row in records)
    answer_types = Counter(type(row["answer"]).__name__ for row in records)

    invalid_evidence: list[dict[str, Any]] = []
    page_counts: dict[ReportKey, int] = {}
    with MarkdownReportStore(reports_file) as reports:
        report_keys = set(reports.keys())
        for key in reports.keys():
            pages = split_markdown_pages(
                reports.read_text(key), source=f"{key.company}/{key.year}.md"
            )
            page_counts[key] = len(pages)

    missing_reports = sorted(task_keys - set(page_counts))
    reports_without_tasks = sorted(set(page_counts) - task_keys)
    for row in records:
        key = ReportKey(row["company"], row["year"])
        count = page_counts.get(key)
        if count is None:
            continue
        bad = [page for page in row["page_numbers"] if page > count]
        if bad:
            invalid_evidence.append(
                {
                    "source_task_id": row["id"],
                    "company": key.company,
                    "year": key.year,
                    "page_count": count,
                    "invalid_source_pages": bad,
                }
            )

    task_doc_page_counts = sorted(page_counts[key] for key in task_keys if key in page_counts)
    quantile_indices = {
        "min": 0,
        "p25": len(task_doc_page_counts) // 4,
        "median": len(task_doc_page_counts) // 2,
        "p75": (3 * len(task_doc_page_counts)) // 4,
        "max": len(task_doc_page_counts) - 1,
    }
    page_quantiles = {
        name: task_doc_page_counts[index]
        for name, index in quantile_indices.items()
        if task_doc_page_counts
    }
    structurally_valid = not missing_reports and not invalid_evidence

    return {
        "dataset": "FinLongDocQA",
        "source_version": "v1.1",
        "source_files": {
            "annotations": str(annotations_file),
            "annotations_sha256": _sha256(annotations_file),
            "reports": str(reports_file),
            "reports_sha256": _sha256(reports_file),
        },
        "annotation_count": len(records),
        "report_count": len(page_counts),
        "company_count": len({key.company for key in page_counts}),
        "task_document_count": len(task_keys),
        "reports_without_tasks_count": len(reports_without_tasks),
        "reports_without_tasks_examples": [
            key.to_dict() for key in reports_without_tasks[:20]
        ],
        "missing_reports": [key.to_dict() for key in missing_reports],
        "invalid_evidence_references": invalid_evidence,
        "duplicate_task_ids": 0,
        "question_type_counts": dict(sorted(type_counts.items())),
        "year_counts": dict(sorted(year_counts.items())),
        "answer_type_counts": dict(sorted(answer_types.items())),
        "evidence_page_count_distribution": {
            str(key): value for key, value in sorted(evidence_cardinality.items())
        },
        "source_evidence_page_range": {
            "min": min(page for row in records for page in row["page_numbers"]),
            "max": max(page for row in records for page in row["page_numbers"]),
        },
        "report_page_count_range": {
            "min": min(page_counts.values()),
            "max": max(page_counts.values()),
        },
        "task_document_page_count_quantiles": page_quantiles,
        "page_markers_contiguous_and_one_based": True,
        "released_report_format": "markdown",
        "released_pdf_count": 0,
        "reference_programs_executed": False,
        "structurally_valid": structurally_valid,
    }
