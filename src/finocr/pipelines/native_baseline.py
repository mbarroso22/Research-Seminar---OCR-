from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Callable

from pypdf import PdfReader

from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.io import iter_jsonl, read_jsonl, write_json, write_jsonl
from finocr.retrieval.bm25 import (
    BM25Index, RetrievalQuery, TOKEN_PATTERN, TOKENIZER_VERSION, normalize_search_text,
)


Progress = Callable[[str], None]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class NativeDocument:
    doc_id: str
    pdf_path: Path
    page_count: int
    sha256: str


def load_native_documents(
    path: Path, *, repository_root: Path, pdf_dir: Path | None = None,
) -> list[NativeDocument]:
    documents = []
    seen = set()
    for row in iter_jsonl(path):
        doc_id, count, source = row.get("doc_id"), row.get("page_count"), row.get("pdf_path")
        metadata = row.get("metadata", {})
        checksum = metadata.get("sha256") if isinstance(metadata, dict) else None
        if not isinstance(doc_id, str) or not doc_id.strip() or doc_id in seen:
            raise ValueError("Document IDs must be nonempty and unique")
        if type(count) is not int or count <= 0:
            raise ValueError(f"{doc_id}: positive integer page_count required")
        if row.get("source_format") != "pdf" or not isinstance(source, str) or not source:
            raise ValueError(f"{doc_id}: a source PDF path is required")
        if not isinstance(checksum, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
            raise ValueError(f"{doc_id}: recorded SHA-256 is required")
        if pdf_dir is not None:
            # PureWindowsPath also handles POSIX separators; never rewrite manifest IDs.
            filename = PureWindowsPath(source).name
            if filename in {"", ".", ".."}:
                raise ValueError(f"{doc_id}: unsafe PDF basename")
            source_path = pdf_dir / filename
        else:
            source_path = Path(source)
            if not source_path.is_absolute():
                if PureWindowsPath(source).is_absolute():
                    raise ValueError("Windows manifest paths on this OS require --pdf-dir")
                source_path = repository_root / source_path
        documents.append(NativeDocument(doc_id, source_path.resolve(), count, checksum.lower()))
        seen.add(doc_id)
    if not documents:
        raise ValueError("Document manifest must be nonempty")
    if len({document.pdf_path for document in documents}) != len(documents):
        raise ValueError("Multiple document IDs resolve to the same PDF")
    return documents


def load_queries(path: Path, document_ids: set[str]) -> list[RetrievalQuery]:
    queries = []
    seen = set()
    for row in iter_jsonl(path):
        query = RetrievalQuery.from_record(row)
        if query.task_id in seen or query.doc_id not in document_ids:
            raise ValueError(f"Duplicate query or unknown report: {query.task_id}")
        seen.add(query.task_id)
        queries.append(query)
    if not queries:
        raise ValueError("Task manifest must contain questions")
    return queries


def load_evidence_labels(path: Path) -> list[dict[str, Any]]:
    # Offline evaluator gets no answer/justification/evidence text, either.
    return [
        {"task_id": row.get("task_id"), "doc_id": row.get("doc_id"),
         "evidence_pages": row.get("evidence_pages")}
        for row in iter_jsonl(path)
    ]


def extract_document(
    document: NativeDocument, *, run_id: str, progress: Progress | None = None,
    progress_every: int = 50,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One report at a time. Any rejected report gets explicit expected-page failures.

    Failure placeholders are not successful extraction or observed physical pages.
    A page failure never renumbers subsequent pages. Empty native text does not
    establish that the physical PDF page is blank.
    """
    started = time.perf_counter()
    observed_sha = None
    final_sha = None
    observed_count = None
    rows = []
    error = None
    pypdf_version = importlib.metadata.version("pypdf")

    def page_row(index: int, text: str, status: str, seconds: float, page_error: str | None,
                 attempted: bool) -> dict[str, Any]:
        return {
            "schema_version": 1, "run_id": run_id, "doc_id": document.doc_id,
            "page_index": index, "page_index_base": 0,
            "document_sha256": observed_sha, "expected_document_sha256": document.sha256,
            "representation": "native_pdf_text", "engine": "pypdf", "engine_version": pypdf_version,
            "extraction_mode": "plain", "raw_text": text,
            "search_text": normalize_search_text(text), "status": status, "error": page_error,
            "raw_character_count": len(text),
            "extraction_attempted": attempted, "elapsed_seconds": seconds,
        }

    try:
        observed_sha = sha256_file(document.pdf_path)
        if observed_sha != document.sha256:
            raise ValueError("checksum_mismatch: PDF differs from the frozen manifest")
        with document.pdf_path.open("rb") as handle:
            reader = PdfReader(handle, strict=False)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("encrypted_pdf: empty password cannot decrypt this report")
            observed_count = len(reader.pages)
            if observed_count != document.page_count:
                raise ValueError(f"page_count_mismatch: expected {document.page_count}, found {observed_count}")
            for index in range(observed_count):
                page_started = time.perf_counter()
                try:
                    text = reader.pages[index].extract_text(extraction_mode="plain") or ""
                    row = page_row(index, text, "ok" if text.strip() else "blank_native_text",
                                   time.perf_counter() - page_started, None, True)
                except Exception as exc:
                    row = page_row(index, "", "page_failed", time.perf_counter() - page_started,
                                   f"{type(exc).__name__}: {exc}", True)
                rows.append(row)
                if progress and (index + 1) % progress_every == 0:
                    progress(f"{document.doc_id}: {index + 1}/{observed_count} pages accounted for")
        # Detect source edits during extraction; never retain text from an unverified revision.
        final_sha = sha256_file(document.pdf_path)
        if final_sha != observed_sha:
            raise ValueError("source_changed: PDF changed during extraction")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        previous_rows = rows
        rows = [page_row(index, "", "document_failed",
                        previous_rows[index]["elapsed_seconds"] if index < len(previous_rows) else 0.0,
                        error, index < len(previous_rows))
                for index in range(document.page_count)]
    counts = Counter(row["status"] for row in rows)
    failed = counts["page_failed"] + counts["document_failed"]
    summary = {
        "doc_id": document.doc_id, "resolved_pdf_path": str(document.pdf_path),
        "expected_sha256": document.sha256, "observed_sha256": observed_sha,
        "post_extraction_sha256": final_sha,
        "expected_page_count": document.page_count, "observed_page_count": observed_count,
        "page_record_count": len(rows), "status_counts": dict(counts),
        "attempted_page_count": sum(row["extraction_attempted"] for row in rows),
        "native_character_count": sum(row["raw_character_count"] for row in rows),
        "blank_native_text_indices": [row["page_index"] for row in rows if row["status"] == "blank_native_text"],
        "failed_page_indices": [row["page_index"] for row in rows if row["status"] in {"page_failed", "document_failed"}],
        "failed_page_count": failed, "error": error,
        "status": "document_failed" if error else "partial_extraction" if failed else "ok",
        "elapsed_seconds": time.perf_counter() - started,
    }
    return rows, summary


def code_provenance(repository_root: Path) -> dict[str, Any]:
    def git(*arguments: str) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(repository_root), *arguments], stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="replace")
        except (OSError, subprocess.CalledProcessError):
            return None
    diff = git("diff", "HEAD", "--binary")
    status = git("status", "--porcelain")
    code_root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for source in sorted(code_root.rglob("*.py")):
        digest.update(source.relative_to(code_root).as_posix().encode("utf-8") + b"\0")
        digest.update(source.read_bytes() + b"\0")
    versions = {}
    for package in ("financial-ocr-research", "pypdf", "cryptography", "fonttools"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    commit = git("rev-parse", "HEAD")
    return {
        "git_commit": commit.strip() if commit else None, "git_dirty": bool(status) if status is not None else None,
        "git_diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff is not None else None,
        "python_source_sha256": digest.hexdigest(), "package_versions": versions,
        "python": sys.version, "platform": platform.platform(),
    }


def run_native_baseline(
    documents_path: str | Path, tasks_path: str | Path, output_dir: str | Path,
    *, repository_root: str | Path = ".", pdf_dir: str | Path | None = None,
    k1: float = 1.2, b: float = 0.75, ks: tuple[int, ...] = (1, 3, 5),
    expected_documents: int | None = None, expected_pages: int | None = None,
    expected_questions: int | None = None, skip_evaluation: bool = False,
    progress: Progress | None = None,
) -> dict[str, Any]:
    # Validate configuration and minimal inputs before creating the run directory.
    BM25Index("configuration_check", [], k1=k1, b=b)
    if not ks or any(type(k) is not int or k <= 0 for k in ks) or len(set(ks)) != len(ks):
        raise ValueError("k values must be distinct positive integers")
    root, output = Path(repository_root).resolve(), Path(output_dir).resolve()
    if (root / ".git").exists() and (output == root or root in output.parents):
        raise ValueError("Save derived run outputs outside the Git repository")
    documents_path, tasks_path = Path(documents_path).resolve(), Path(tasks_path).resolve()
    document_hash, task_hash = sha256_file(documents_path), sha256_file(tasks_path)
    documents = load_native_documents(documents_path, repository_root=root,
                                      pdf_dir=Path(pdf_dir).resolve() if pdf_dir else None)
    queries = load_queries(tasks_path, {doc.doc_id for doc in documents})
    totals = (len(documents), sum(doc.page_count for doc in documents), len(queries))
    for name, actual, expected in zip(
        ("documents", "pages", "questions"), totals,
        (expected_documents, expected_pages, expected_questions),
    ):
        if expected is not None and (type(expected) is not int or expected <= 0 or expected != actual):
            raise ValueError(f"Expected {expected} {name}; manifest contains {actual}")
    if document_hash != sha256_file(documents_path) or task_hash != sha256_file(tasks_path):
        raise ValueError("Input manifests changed during loading")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    manifest = {
        "schema_version": 1, "run_id": run_id, "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "condition": "N_native_text_bm25", "experimental_group": "development_pilot",
        "page_index_base": 0, "code": code_provenance(root),
        "inputs": {"documents": {"path": str(documents_path), "sha256": document_hash},
                   "tasks": {"path": str(tasks_path), "sha256": task_hash}},
        "configuration": {
            "engine": "pypdf", "extraction_mode": "plain", "pdf_reader_strict": False,
            "encrypted_pdf_policy": "try empty password; otherwise record document failure",
            "normalization": "NFKC; Unicode minus to ASCII minus; whitespace collapse; raw retained",
            "tokenizer_version": TOKENIZER_VERSION, "token_pattern": TOKEN_PATTERN,
            "k1": k1, "b": b, "ks": sorted(ks), "query_term_frequency": "binary",
            "idf": "log(1 + (N - df + 0.5) / (df + 0.5))",
            "candidate_policy": "all physical page indices; empty/failed page text is empty",
            "tie_policy": "score descending, zero-based page_index ascending; zero ties retained",
            "query_fields": ["task_id", "doc_id", "question"], "full_ranking": True,
            "report_order": [doc.doc_id for doc in documents], "concurrency": 1,
            "skip_evaluation": skip_evaluation, "resume": False,
        },
        "manifest_totals": dict(zip(("documents", "pages", "questions"), totals)),
        "stages": {},
    }
    write_json(output / "run_manifest.json", manifest)
    try:
        query_path = output / "retrieval_queries.jsonl"
        write_jsonl(query_path, (query.to_dict() for query in queries))
        manifest["inputs"]["retrieval_queries"] = {"path": query_path.name, "sha256": sha256_file(query_path)}
        summaries, page_files = [], []
        stage_started = time.perf_counter()
        for document in documents:
            if progress:
                progress(f"Extracting {document.doc_id} ({document.page_count} expected pages)")
            rows, summary = extract_document(document, run_id=run_id, progress=progress)
            # Hash-only filenames are Windows-safe even when doc_id contains ':' or '/'.
            filename = hashlib.sha256(document.doc_id.encode("utf-8")).hexdigest() + ".jsonl"
            page_file = output / "pages" / filename
            write_jsonl(page_file, rows)
            summary["pages_file"] = page_file.relative_to(output).as_posix()
            summary["pages_sha256"] = sha256_file(page_file)
            summaries.append(summary)
            page_files.append(page_file)
            # Completed reports survive a later interruption; no implicit reuse/resume.
            write_json(output / "extraction_summary.json", {"status": "running", "documents": summaries})
            if progress:
                progress(f"{document.doc_id}: {summary['status']}; {summary['status_counts']}")
        write_jsonl(output / "native_pages.jsonl", (row for path in page_files for row in iter_jsonl(path)))
        counts: Counter[str] = Counter()
        for summary in summaries:
            counts.update(summary["status_counts"])
        extraction = {
            "status": "complete" if not counts["page_failed"] and not counts["document_failed"] else "complete_with_failures",
            "document_count": len(summaries), "expected_page_count": totals[1],
            "page_record_count": sum(summary["page_record_count"] for summary in summaries),
            "attempted_page_count": sum(summary["attempted_page_count"] for summary in summaries),
            "status_counts": dict(counts), "failed_page_count": counts["page_failed"] + counts["document_failed"],
            "documents": summaries, "elapsed_seconds": time.perf_counter() - stage_started,
            "blank_text_meaning": "no native text; may be an image/scanned page, not a verified blank PDF page",
        }
        write_json(output / "extraction_summary.json", extraction)
        manifest["stages"]["extraction"] = {"status": extraction["status"], "elapsed_seconds": extraction["elapsed_seconds"]}
        write_json(output / "run_manifest.json", manifest)

        # Retrieval reloads only sanitized queries and extracted page records.
        safe_queries = [RetrievalQuery.from_record(row) for row in iter_jsonl(query_path)]
        by_document: dict[str, list[RetrievalQuery]] = {}
        for query in safe_queries:
            by_document.setdefault(query.doc_id, []).append(query)
        predictions_by_id = {}
        indexing_seconds = 0.0
        for document, summary, path in zip(documents, summaries, page_files):
            report_queries = by_document.get(document.doc_id, [])
            if not report_queries:
                continue
            index_started = time.perf_counter()
            index = BM25Index(document.doc_id,
                              ((row["page_index"], row["search_text"]) for row in iter_jsonl(path)), k1=k1, b=b)
            indexing_seconds += time.perf_counter() - index_started
            for query in report_queries:
                query_started = time.perf_counter()
                ranking = [] if summary["status"] == "document_failed" else index.rank(query)
                no_match = not ranking or ranking[0]["score"] == 0
                predictions_by_id[query.task_id] = {
                    "schema_version": 1, "run_id": run_id, "task_id": query.task_id,
                    "doc_id": query.doc_id, "condition": "N_native_text_bm25", "page_index_base": 0,
                    "page_count": document.page_count, "status": summary["status"],
                    "error": summary["error"], "no_match": no_match,
                    "positive_score_page_count": sum(row["score"] > 0 for row in ranking),
                    "ranked_pages": ranking, "elapsed_seconds": time.perf_counter() - query_started,
                }
        predictions = [predictions_by_id[query.task_id] for query in safe_queries]
        prediction_path = output / "retrieval_predictions.jsonl"
        write_jsonl(prediction_path, predictions)
        manifest["stages"]["retrieval"] = {
            "status": "complete", "question_count": len(predictions), "indexing_seconds": indexing_seconds,
            "query_seconds": sum(row["elapsed_seconds"] for row in predictions),
        }
        write_json(output / "run_manifest.json", manifest)
        if not skip_evaluation:
            # Only now read gold labels, after predictions have been atomically saved.
            if sha256_file(tasks_path) != task_hash:
                raise ValueError("Task annotations changed after retrieval; refusing evaluation")
            evaluation_started = time.perf_counter()
            metrics = evaluate_retrieval(read_jsonl(prediction_path), load_evidence_labels(tasks_path), ks=ks)
            if sha256_file(tasks_path) != task_hash:
                raise ValueError("Task annotations changed during evaluation")
            write_json(output / "retrieval_metrics.json", metrics)
            manifest["stages"]["evaluation"] = {"status": "complete", "elapsed_seconds": time.perf_counter() - evaluation_started}
        else:
            manifest["stages"]["evaluation"] = {"status": "skipped"}
        if sha256_file(documents_path) != document_hash or sha256_file(tasks_path) != task_hash:
            raise ValueError("Input manifests changed during run")
        manifest["status"] = extraction["status"]
        manifest["artifacts"] = {
            path.name: {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for path in sorted(output.iterdir()) if path.is_file() and path.name != "run_manifest.json"
        }
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["elapsed_seconds"] = time.perf_counter() - started
        write_json(output / "run_manifest.json", manifest)
    return {
        "status": manifest["status"], "run_id": run_id, "output_dir": str(output),
        "documents": len(documents), "page_records": extraction["page_record_count"],
        "attempted_pages": extraction["attempted_page_count"], "questions": len(predictions),
        "failed_pages": extraction["failed_page_count"], "evaluation": manifest["stages"]["evaluation"]["status"],
    }
