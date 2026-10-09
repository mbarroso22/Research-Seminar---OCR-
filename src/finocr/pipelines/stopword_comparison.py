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
from finocr.retrieval.query_expansion import expand_query, policy_record


def _compare_cached(
    baseline_dir: str | Path, output_dir: str | Path, *, tasks_path: str | Path | None = None,
    repository_root: str | Path = ".", progress: Callable[[str], None] | None = None,
    expand_queries: bool = False, stopword_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Shared full-cohort runner for the stopword and question-expansion ablations.

    Gold labels are read only after all rankings have been saved. This deliberately
    rejects incomplete page exports and altered baseline artifacts. No PDF, OCR,
    manually chosen page subset, or answer generation is used. Expansion is an
    explicit opt-in; the public stopword experiment keeps its original behavior.
    """
    overall_started = time.perf_counter()
    overall_started_utc = datetime.now(timezone.utc).isoformat()
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
    reference = None
    if expand_queries:
        if stopword_dir is None:
            raise ValueError("The completed stopword comparison directory is required")
        reference = _load_stopword_reference(Path(stopword_dir).resolve(), old_manifest, verified,
                                            task_hash, sha256_file(baseline / "run_manifest.json"))
    transformed, expansion_audit = {}, []
    transformation_started = time.perf_counter()
    if expand_queries:
        for query in queries:
            expanded, audit = expand_query(query)
            transformed[query.task_id] = expanded
            expansion_audit.append(audit)
    transformation_seconds = time.perf_counter() - transformation_started if expand_queries else 0.0
    output.mkdir(parents=True, exist_ok=False)
    started = overall_started if expand_queries else time.perf_counter()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    manifest = {
        "schema_version": 1, "run_id": run_id, "status": "running",
        "baseline_run_id": old_manifest["run_id"], "baseline_directory": str(baseline),
        "baseline_manifest_sha256": sha256_file(baseline / "run_manifest.json"),
        "experimental_group": "development_pilot", "page_index_base": 0,
        "started_utc": overall_started_utc if expand_queries else datetime.now(timezone.utc).isoformat(),
        "code": code_provenance(root),
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
        if expand_queries:
            manifest["experiment"] = "N_native_text_bm25_question_expansion"
            manifest["stopword_reference"] = {key: reference[key] for key in ("run_id", "manifest_sha256", "artifacts")}
            manifest["configuration"].update({
                "change": "fixed financial-term expansion of questions only, on the reproduced stopword index",
                "query_expansion": True, "expansion_policy": policy_record(),
                "page_text_transformation": "unchanged from stopword baseline",
                "primary_comparison": "question_expansion minus stopwords",
            })
            manifest["query_transformation_seconds"] = transformation_seconds
            manifest["initial_validation_seconds"] = transformation_started - overall_started
            manifest["timing_policy"] = "wall time includes validation, query expansion, control reproduction, ranking, scoring, and output; original PDF extraction is shared prior ingestion"
            manifest["transformed_question_count"] = sum(bool(row["added_terms"]) for row in expansion_audit)
            write_json(output / "run_manifest.json", manifest)
        by_doc: dict[str, list[RetrievalQuery]] = {}
        for query in queries:
            by_doc.setdefault(query.doc_id, []).append(query)
        reproduced, variant, expanded_predictions = {}, {}, {}
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
                conditions = [
                    ("N_native_text_bm25_reproduced", original_index, reproduced, query),
                    ("N_native_text_bm25_stopwords", stop_index, variant, query),
                ]
                if expand_queries:
                    conditions.append(("N_native_text_bm25_question_expansion", stop_index,
                                       expanded_predictions, transformed[query.task_id]))
                for condition, index, destination, retrieval_query in conditions:
                    query_started = time.perf_counter()
                    ranking = index.rank(retrieval_query)
                    elapsed = time.perf_counter() - query_started
                    if destination is reproduced:
                        old = old_by_id[query.task_id]
                        previous = old["ranked_pages"]
                        if (old["doc_id"] != doc_id or len(previous) != len(ranking)
                                or any(a["page_index"] != b["page_index"] or not math.isclose(
                                    a["score"], b["score"], rel_tol=1e-12, abs_tol=1e-12)
                                    for a, b in zip(previous, ranking))):
                            raise ValueError(f"Original baseline ranking failed reproduction: {query.task_id}")
                    elif destination is variant and expand_queries:
                        saved = reference["predictions"].get(query.task_id)
                        if (saved is None or saved["doc_id"] != doc_id
                                or saved["page_count"] != len(records) or saved["page_index_base"] != 0
                                or saved["status"] != "ok" or saved["run_id"] != reference["run_id"]
                                or saved["error"] is not None
                                or saved["no_match"] != (not ranking or ranking[0]["score"] == 0)
                                or saved["positive_score_page_count"] != sum(row["score"] > 0 for row in ranking)
                                or saved["condition"] != "N_native_text_bm25_stopwords"
                                or len(saved["ranked_pages"]) != len(ranking)
                                or any(a["page_index"] != b["page_index"] or not math.isclose(
                                    a["score"], b["score"], rel_tol=1e-12, abs_tol=1e-12)
                                    for a, b in zip(saved["ranked_pages"], ranking))):
                            raise ValueError(f"Stopword baseline ranking failed reproduction: {query.task_id}")
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
        if expand_queries and set(reference["predictions"]) != set(by_task):
            raise ValueError("Stopword baseline task IDs do not match the original cohort")
        original_rows = [reproduced[q.task_id] for q in queries]
        variant_rows = [variant[q.task_id] for q in queries]
        write_jsonl(output / "baseline_reproduced_predictions.jsonl", original_rows)
        write_jsonl(output / "stopword_predictions.jsonl", variant_rows)
        write_jsonl(output / "retrieval_queries.jsonl", (q.to_dict() for q in queries))
        manifest["baseline_reproduced"] = True
        if expand_queries:
            expanded_rows = [expanded_predictions[q.task_id] for q in queries]
            write_jsonl(output / "expanded_predictions.jsonl", expanded_rows)
            write_jsonl(output / "expanded_retrieval_queries.jsonl", (transformed[q.task_id].to_dict() for q in queries))
            write_jsonl(output / "query_expansion_audit.jsonl", expansion_audit)
            manifest["stopword_baseline_reproduced"] = True
        # Annotations are first parsed here, after all prediction files are saved.
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
        if expand_queries:
            reference_metrics = read_json(reference["directory"] / "comparison_metrics.json")
            if (baseline_metrics != reference_metrics["baseline"]
                    or stopword_metrics != reference_metrics["stopwords"]):
                raise ValueError("Saved stopword reference metrics do not reproduce")
            expanded_metrics = evaluate_retrieval(expanded_rows, labels, ks=tuple(config["ks"]))
            comparison["question_expansion"] = expanded_metrics
            comparison["delta_at_k"] = {
                control: {
                    k: {metric: expanded_metrics["at_k"][k][metric] - values[metric]
                        for metric in ("macro_evidence_recall", "any_evidence_hit_rate", "all_evidence_coverage_rate")}
                    for k, values in metrics["at_k"].items()
                } for control, metrics in (("baseline", baseline_metrics), ("stopwords", stopword_metrics))
            }
            comparison["interpretation"] = "development-only question-term expansion; not answer correctness or held-out evaluation"
        if sha256_file(tasks) != task_hash:
            raise ValueError("Task annotations changed during scoring")
        write_json(output / "comparison_metrics.json", comparison)
        # Verify immutable inputs again; reject changes during the run.
        for name, entry in verified.items():
            if sha256_file(baseline / name) != entry["sha256"]:
                raise ValueError(f"Baseline artifact changed during comparison: {name}")
        if sha256_file(baseline / "run_manifest.json") != manifest["baseline_manifest_sha256"]:
            raise ValueError("Baseline manifest changed during comparison")
        if expand_queries:
            _check_reference_unchanged(reference)
        manifest["status"] = "complete"
        manifest["indexing_seconds"] = index_seconds
        manifest["query_seconds"] = {
            "baseline": sum(row["elapsed_seconds"] for row in original_rows),
            "stopwords": sum(row["elapsed_seconds"] for row in variant_rows),
        }
        if expand_queries:
            manifest["query_seconds"]["question_expansion"] = sum(row["elapsed_seconds"] for row in expanded_rows)
            manifest["indexing_seconds"]["question_expansion_incremental"] = 0.0
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
            "questions": len(queries), **({"stopword_baseline_reproduced": True,
                "transformed_questions": manifest["transformed_question_count"]} if expand_queries else {})}


def _load_stopword_reference(directory, original, inputs, task_hash, baseline_manifest_hash):
    path = directory / "run_manifest.json"
    reference_manifest = read_json(path)
    config = reference_manifest.get("configuration", {})
    if (reference_manifest.get("status") != "complete"
            or reference_manifest.get("baseline_reproduced") is not True
            or reference_manifest.get("baseline_run_id") != original["run_id"]
            or reference_manifest.get("baseline_manifest_sha256") != baseline_manifest_hash
            or reference_manifest.get("task_sha256") != task_hash
            or reference_manifest.get("manifest_totals") != original["manifest_totals"]
            or reference_manifest.get("page_index_base") != 0
            or config.get("query_expansion") is not False
            or config.get("stemming") is not False
            or config.get("year_normalization") != "unchanged"
            or config.get("stopword_version") != STOPWORD_VERSION
            or config.get("stopwords") != sorted(STOPWORDS)
            or config.get("stopword_sha256") != hashlib.sha256("\n".join(sorted(STOPWORDS)).encode()).hexdigest()
            or any(config.get(key) != original["configuration"].get(key)
                   for key in ("k1", "b", "ks", "candidate_policy", "tie_policy", "query_fields"))
            or reference_manifest.get("inputs") != inputs):
        raise ValueError("Stopword reference must use the same frozen baseline, cohort, and policy")
    verified = {}
    for name in ("stopword_predictions.jsonl", "baseline_reproduced_predictions.jsonl",
                 "retrieval_queries.jsonl", "comparison_metrics.json"):
        file = directory / name
        actual = {"sha256": sha256_file(file), "size_bytes": file.stat().st_size}
        if actual != reference_manifest["artifacts"][name]:
            raise ValueError(f"Stopword reference artifact changed or incomplete: {name}")
        verified[name] = actual
    if verified["retrieval_queries.jsonl"] != inputs["retrieval_queries.jsonl"]:
        raise ValueError("Stopword reference query projection changed")
    predictions = read_jsonl(directory / "stopword_predictions.jsonl")
    by_id = {row["task_id"]: row for row in predictions}
    if len(by_id) != len(predictions):
        raise ValueError("Duplicate stopword reference task IDs")
    return {"directory": directory, "manifest_sha256": sha256_file(path),
            "baseline_manifest_sha256": reference_manifest["baseline_manifest_sha256"],
            "run_id": reference_manifest["run_id"], "artifacts": verified,
            "predictions": by_id}


def _check_reference_unchanged(reference):
    directory = reference["directory"]
    if sha256_file(directory / "run_manifest.json") != reference["manifest_sha256"]:
        raise ValueError("Stopword reference manifest changed during comparison")
    for name, entry in reference["artifacts"].items():
        if sha256_file(directory / name) != entry["sha256"]:
            raise ValueError(f"Stopword reference artifact changed during comparison: {name}")


def compare_stopwords(
    baseline_dir: str | Path, output_dir: str | Path, *, tasks_path: str | Path | None = None,
    repository_root: str | Path = ".", progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the original stopword-only experiment; its default policy is unchanged."""
    return _compare_cached(baseline_dir, output_dir, tasks_path=tasks_path,
                           repository_root=repository_root, progress=progress)


def compare_query_expansion(
    baseline_dir: str | Path, stopword_dir: str | Path, output_dir: str | Path, *,
    tasks_path: str | Path | None = None, repository_root: str | Path = ".",
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Reproduce both frozen controls, then add only question-derived search terms."""
    return _compare_cached(baseline_dir, output_dir, tasks_path=tasks_path,
                           repository_root=repository_root, progress=progress,
                           expand_queries=True, stopword_dir=stopword_dir)
