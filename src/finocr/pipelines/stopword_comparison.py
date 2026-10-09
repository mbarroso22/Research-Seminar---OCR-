from __future__ import annotations

import hashlib
import math
import time
import uuid
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Callable

from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.io import iter_jsonl, read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance, load_evidence_labels, sha256_file
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, normalize_search_text
from finocr.retrieval.stopwords import STOPWORDS, STOPWORD_VERSION, tokenize_without_stopwords


def compare_stopwords(
    baseline_dir: str | Path, output_dir: str | Path, *, tasks_path: str | Path | None = None,
    repository_root: str | Path = ".", progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Reproduce the frozen full-report baseline, then remove only function words.

    Gold labels are read only after both rankings have been saved. This deliberately
    rejects incomplete page exports and altered baseline artifacts. No PDF, OCR,
    query rewriting, manually chosen page subset, or answer generation is used.
    """
    baseline, output, root = Path(baseline_dir).resolve(), Path(output_dir).resolve(), Path(repository_root).resolve()
    if (root / ".git").exists() and (output == root or root in output.parents):
        raise ValueError("Save comparison outputs outside the Git repository")
    old_manifest = read_json(baseline / "run_manifest.json")
    if old_manifest.get("status") != "complete" or old_manifest.get("condition") != "N_native_text_bm25":
        raise ValueError("A complete original native-text/BM25 run is required")
    config = old_manifest["configuration"]
    if config.get("tokenizer_version") != "unicode-financial-v1" or not config.get("full_ranking"):
        raise ValueError("Unsupported baseline tokenizer/ranking configuration")
    verified = {}
    for name in ("native_pages.jsonl", "retrieval_queries.jsonl", "retrieval_predictions.jsonl", "extraction_summary.json"):
        path = baseline / name
        expected = old_manifest["artifacts"][name]
        checksum = sha256_file(path)
        if checksum != expected["sha256"] or path.stat().st_size != expected["size_bytes"]:
            raise ValueError(f"Baseline artifact changed or incomplete: {name}")
        verified[name] = {"sha256": checksum, "size_bytes": path.stat().st_size}
    totals = old_manifest["manifest_totals"]
    extraction = read_json(baseline / "extraction_summary.json")
    documents = extraction["documents"]
    if (len(documents) != totals["documents"] or extraction["page_record_count"] != totals["pages"]
            or extraction["failed_page_count"] or extraction["attempted_page_count"] != totals["pages"]):
        raise ValueError("Complete extraction coverage is required")
    docs = {row["doc_id"]: row for row in documents}
    if len(docs) != len(documents):
        raise ValueError("Duplicate extracted report IDs")
    queries = []
    for row in iter_jsonl(baseline / "retrieval_queries.jsonl"):
        if set(row) != {"task_id", "doc_id", "question"}:
            raise ValueError("Retrieval query file must contain only the three allowed fields")
        queries.append(RetrievalQuery.from_record(row))
    by_task = {query.task_id: query for query in queries}
    if len(by_task) != len(queries) or len(queries) != totals["questions"] or any(q.doc_id not in docs for q in queries):
        raise ValueError("Baseline queries do not match extracted reports/counts")
    old_predictions = read_jsonl(baseline / "retrieval_predictions.jsonl")
    old_by_id = {row["task_id"]: row for row in old_predictions}
    if len(old_predictions) != len(old_by_id) or set(old_by_id) != set(by_task):
        raise ValueError("Baseline predictions do not match query IDs")
    tasks = Path(tasks_path or old_manifest["inputs"]["tasks"]["path"]).resolve()
    task_hash = sha256_file(tasks)
    if task_hash != old_manifest["inputs"]["tasks"]["sha256"]:
        raise ValueError("Use the original frozen task annotations for this comparison")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    manifest = {
        "schema_version": 1, "run_id": run_id, "status": "running",
        "baseline_run_id": old_manifest["run_id"], "baseline_directory": str(baseline),
        "baseline_manifest_sha256": sha256_file(baseline / "run_manifest.json"),
        "experimental_group": "development_pilot", "page_index_base": 0,
        "started_utc": datetime.now(timezone.utc).isoformat(), "code": code_provenance(root),
        "inputs": verified, "task_sha256": task_hash, "manifest_totals": totals,
        "configuration": {
            "k1": config["k1"], "b": config["b"], "ks": config["ks"],
            "change": "remove the fixed function-word list from page and question tokens",
            "stopword_version": STOPWORD_VERSION, "stopwords": sorted(STOPWORDS),
            "stopword_sha256": hashlib.sha256("\n".join(sorted(STOPWORDS)).encode()).hexdigest(),
            "year_normalization": "unchanged", "stemming": False, "query_expansion": False,
            "candidate_policy": config["candidate_policy"], "tie_policy": config["tie_policy"],
            "query_fields": ["task_id", "doc_id", "question"],
            "baseline_reproduction_tolerance": {"relative": 1e-12, "absolute": 1e-12},
            "ingestion_cost_policy": "reuse native text; original extraction cost remains attributed to shared ingestion",
        },
    }
    write_json(output / "run_manifest.json", manifest)
    try:
        by_doc: dict[str, list[RetrievalQuery]] = {}
        for query in queries:
            by_doc.setdefault(query.doc_id, []).append(query)
        reproduced, variant = {}, {}
        seen_docs = set()
        total_pages = 0
        index_seconds = {"baseline": 0.0, "stopwords": 0.0}
        for doc_id, group in groupby(iter_jsonl(baseline / "native_pages.jsonl"), lambda row: row["doc_id"]):
            if doc_id not in docs or doc_id in seen_docs:
                raise ValueError("Native pages must have contiguous unique report groups")
            seen_docs.add(doc_id)
            records = list(group)
            document = docs[doc_id]
            if [row["page_index"] for row in records] != list(range(document["expected_page_count"])):
                raise ValueError(f"Missing, duplicated, or reordered native pages: {doc_id}")
            for row in records:
                if (row["run_id"] != old_manifest["run_id"] or row["page_index_base"] != 0
                        or row["status"] not in {"ok", "blank_native_text"}
                        or row["document_sha256"] != document["expected_sha256"]
                        or row["search_text"] != normalize_search_text(row["raw_text"])):
                    raise ValueError(f"Invalid cached native page: {doc_id}/{row['page_index']}")
            total_pages += len(records)
            if progress:
                progress(f"Validated cached {doc_id}: {len(records)} pages")
            report_queries = by_doc.get(doc_id, [])
            if not report_queries:
                continue
            page_text = [(row["page_index"], row["search_text"]) for row in records]
            index_started = time.perf_counter()
            original_index = BM25Index(doc_id, page_text, k1=config["k1"], b=config["b"])
            index_seconds["baseline"] += time.perf_counter() - index_started
            index_started = time.perf_counter()
            stop_index = BM25Index(doc_id, page_text, k1=config["k1"], b=config["b"], tokenizer=tokenize_without_stopwords)
            index_seconds["stopwords"] += time.perf_counter() - index_started
            for query in report_queries:
                for condition, index, destination in (
                    ("N_native_text_bm25_reproduced", original_index, reproduced),
                    ("N_native_text_bm25_stopwords", stop_index, variant),
                ):
                    query_started = time.perf_counter()
                    ranking = index.rank(query)
                    elapsed = time.perf_counter() - query_started
                    if destination is reproduced:
                        old = old_by_id[query.task_id]
                        previous = old["ranked_pages"]
                        if (old["doc_id"] != doc_id or len(previous) != len(ranking)
                                or any(a["page_index"] != b["page_index"] or not math.isclose(
                                    a["score"], b["score"], rel_tol=1e-12, abs_tol=1e-12)
                                    for a, b in zip(previous, ranking))):
                            raise ValueError(f"Original baseline ranking failed reproduction: {query.task_id}")
                    destination[query.task_id] = {
                        "schema_version": 1, "run_id": run_id, "condition": condition,
                        "task_id": query.task_id, "doc_id": doc_id, "page_index_base": 0,
                        "page_count": len(records), "status": "ok", "error": None,
                        "no_match": not ranking or ranking[0]["score"] == 0,
                        "positive_score_page_count": sum(row["score"] > 0 for row in ranking),
                        "ranked_pages": ranking, "elapsed_seconds": elapsed,
                    }
        if seen_docs != set(docs) or total_pages != totals["pages"]:
            raise ValueError("Cached native pages do not cover the full baseline cohort")
        original_rows = [reproduced[q.task_id] for q in queries]
        variant_rows = [variant[q.task_id] for q in queries]
        write_jsonl(output / "baseline_reproduced_predictions.jsonl", original_rows)
        write_jsonl(output / "stopword_predictions.jsonl", variant_rows)
        write_jsonl(output / "retrieval_queries.jsonl", (q.to_dict() for q in queries))
        manifest["baseline_reproduced"] = True
        # Annotations are first parsed here, after both prediction files are saved.
        if sha256_file(tasks) != task_hash:
            raise ValueError("Task annotations changed before scoring")
        labels = load_evidence_labels(tasks)
        baseline_metrics = evaluate_retrieval(original_rows, labels, ks=tuple(config["ks"]))
        stopword_metrics = evaluate_retrieval(variant_rows, labels, ks=tuple(config["ks"]))
        if sha256_file(tasks) != task_hash:
            raise ValueError("Task annotations changed during scoring")
        comparison = {
            "baseline": baseline_metrics, "stopwords": stopword_metrics,
            "delta_at_k": {
                key: {metric: stopword_metrics["at_k"][key][metric] - values[metric]
                      for metric in ("macro_evidence_recall", "any_evidence_hit_rate", "all_evidence_coverage_rate")}
                for key, values in baseline_metrics["at_k"].items()
            },
            "interpretation": "development-only function-word ablation; metrics are not answer correctness",
        }
        write_json(output / "comparison_metrics.json", comparison)
        # Verify immutable inputs again; reject changes during the run.
        for name, entry in verified.items():
            if sha256_file(baseline / name) != entry["sha256"]:
                raise ValueError(f"Baseline artifact changed during comparison: {name}")
        if sha256_file(baseline / "run_manifest.json") != manifest["baseline_manifest_sha256"]:
            raise ValueError("Baseline manifest changed during comparison")
        manifest["status"] = "complete"
        manifest["indexing_seconds"] = index_seconds
        manifest["query_seconds"] = {
            "baseline": sum(row["elapsed_seconds"] for row in original_rows),
            "stopwords": sum(row["elapsed_seconds"] for row in variant_rows),
        }
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
    return {"status": "complete", "run_id": run_id, "output_dir": str(output),
            "baseline_reproduced": True, "documents": len(docs), "page_records": total_pages,
            "questions": len(queries)}
