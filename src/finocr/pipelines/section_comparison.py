"""Compare source-only heading cues against a reproduced frozen expansion run."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from itertools import groupby
import hashlib
import math
from pathlib import Path
import time
import uuid

from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.io import iter_jsonl, read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance, load_evidence_labels, sha256_file
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, normalize_search_text, TOKENIZER_VERSION, TOKEN_PATTERN
from finocr.retrieval.query_expansion import expand_query, policy_record
from finocr.retrieval.section_context import (
    SourcePage, build_section_context, rank_with_section_context, section_policy_record,
)
from finocr.retrieval.stopwords import STOPWORDS, STOPWORD_VERSION, tokenize_without_stopwords


FROZEN_EXPANSION_SHA256 = "80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3"
_PREDICTIONS = {"baseline": "baseline_reproduced_predictions.jsonl",
                "stopwords": "stopword_predictions.jsonl", "question_expansion": "expanded_predictions.jsonl"}


def _require(value, message):
    if not value:
        raise ValueError(message)


def _by_task(rows, expected):
    result = {row["task_id"]: row for row in rows}
    _require(len(result) == len(rows) and set(result) == expected, "Artifact task coverage mismatch")
    return result


def _check_saved(saved, query, ranking, run_id, condition):
    _require(saved["doc_id"] == query.doc_id and type(saved["page_count"]) is int and saved["page_count"] == len(ranking)
             and type(saved["page_index_base"]) is int and saved["page_index_base"] == 0 and saved["status"] == "ok"
             and saved["run_id"] == run_id and saved["condition"] == condition
             and saved["error"] is None
             and type(saved["no_match"]) is bool and saved["no_match"] == (ranking[0]["score"] == 0)
             and saved["positive_score_page_count"] == sum(r["score"] > 0 for r in ranking),
             "Control prediction metadata does not reproduce")
    previous = saved["ranked_pages"]
    _require(len(previous) == len(ranking), "Incomplete control ranking")
    for left, right in zip(previous, ranking):
        _require(type(left["page_index"]) is int and left["page_index"] == right["page_index"]
                 and type(left["score"]) in (int, float) and math.isfinite(left["score"])
                 and math.isclose(left["score"], right["score"],
                     rel_tol=1e-12, abs_tol=1e-12), f"Control ranking failed reproduction: {query.task_id}")


def _validate_pages(records, doc, native):
    count = doc["expected_page_count"]
    _require([r["page_index"] for r in records] == list(range(count))
             and all(type(r["page_index"]) is int for r in records), "Incomplete/duplicate/reordered native pages")
    _require(count == doc["observed_page_count"] == doc["page_record_count"] == doc["attempted_page_count"]
             and doc["failed_page_count"] == 0, "Extraction page accounting mismatch")
    for row in records:
        _require(row["run_id"] == native["run_id"] and row["page_index_base"] == 0
                 and row["document_sha256"] == row["expected_document_sha256"] == doc["expected_sha256"]
                 == doc["observed_sha256"] == doc["post_extraction_sha256"]
                 and row["engine"] == "pypdf" and row["extraction_mode"] == "plain"
                 and row["engine_version"] == native["code"]["package_versions"]["pypdf"]
                 and row["representation"] == "native_pdf_text" and row["error"] is None
                 and row["extraction_attempted"] is True and isinstance(row["raw_text"], str)
                 and row["raw_character_count"] == len(row["raw_text"])
                 and row["search_text"] == normalize_search_text(row["raw_text"])
                 and row["status"] == ("ok" if row["search_text"] else "blank_native_text"),
                 "Native page provenance/text mismatch")
    _require(dict(Counter(r["status"] for r in records)) == doc["status_counts"]
             and sum(r["raw_character_count"] for r in records) == doc["native_character_count"]
             and [r["page_index"] for r in records if not r["search_text"]] == doc["blank_native_text_indices"],
             "Native summary mismatch")


def _compare_section_context(baseline_dir, expansion_dir, output_dir, *, tasks_path=None,
                            repository_root=".", progress=None):
    started, started_utc = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    baseline, reference, output, root = (Path(p).resolve() for p in
                                        (baseline_dir, expansion_dir, output_dir, repository_root))
    if (root / ".git").exists() and (root == output or root in output.parents):
        raise ValueError("Save section-comparison outputs outside the Git repository")
    _require(output != baseline and output != reference and baseline not in output.parents
             and reference not in output.parents, "Keep new outputs outside existing run directories")
    if output.exists():
        raise FileExistsError("Output directory exists; choose a new immutable run directory")
    verified = {}

    def verify(path, expected=None):
        entry = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        _require(expected is None or entry == expected, f"Input artifact checksum/size mismatch: {path.name}")
        verified[path] = entry
        return entry

    def verify_unchanged():
        for path, expected in verified.items():
            _require({"sha256": sha256_file(path), "size_bytes": path.stat().st_size} == expected,
                     f"Input changed during section comparison: {path.name}")

    native_identity, expansion_identity = verify(baseline / "run_manifest.json"), verify(reference / "run_manifest.json")
    native, expansion = read_json(baseline / "run_manifest.json"), read_json(reference / "run_manifest.json")
    config, ref_config = native["configuration"], expansion["configuration"]
    _require(native["status"] == "complete" and native["condition"] == "N_native_text_bm25"
             and native["page_index_base"] == 0 and config["full_ranking"] is True
             and config["tokenizer_version"] == TOKENIZER_VERSION
             and config["token_pattern"] == TOKEN_PATTERN
             and config["engine"] == "pypdf" and config["extraction_mode"] == "plain"
             and config["k1"] == 1.2 and config["b"] == 0.75 and config["ks"] == [1, 3, 5]
             and config["query_fields"] == ["task_id", "doc_id", "question"]
             and config["candidate_policy"] == "all physical page indices; empty/failed page text is empty"
             and config["tie_policy"] == "score descending, zero-based page_index ascending; zero ties retained",
             "Unsupported native run")
    _require(expansion["status"] == "complete" and expansion["experiment"] == "N_native_text_bm25_question_expansion"
             and expansion["baseline_reproduced"] is True and expansion["stopword_baseline_reproduced"] is True
             and expansion["baseline_run_id"] == native["run_id"]
             and expansion["baseline_manifest_sha256"] == native_identity["sha256"]
             and expansion["manifest_totals"] == native["manifest_totals"] and expansion["page_index_base"] == 0,
             "Expansion reference must use the same complete native run and cohort")
    _require(policy_record()["sha256"] == FROZEN_EXPANSION_SHA256
             and ref_config["expansion_policy"] == policy_record() and ref_config["query_expansion"] is True
             and ref_config["stemming"] is False and ref_config["year_normalization"] == "unchanged"
             and ref_config["page_text_transformation"] == "unchanged from stopword baseline"
             and ref_config["stopword_version"] == STOPWORD_VERSION and ref_config["stopwords"] == sorted(STOPWORDS)
             and ref_config["stopword_sha256"] == hashlib.sha256("\n".join(sorted(STOPWORDS)).encode()).hexdigest()
             and all(ref_config[key] == config[key] for key in ("k1", "b", "ks", "query_fields", "candidate_policy", "tie_policy")),
             "Frozen expansion/control policy mismatch")
    native_inputs = {name: verify(baseline / name, native["artifacts"][name]) for name in
                     ("native_pages.jsonl", "extraction_summary.json", "retrieval_queries.jsonl", "retrieval_predictions.jsonl")}
    _require(expansion["inputs"] == native_inputs, "Expansion reference input lineage mismatch")
    for name in (*_PREDICTIONS.values(), "retrieval_queries.jsonl", "expanded_retrieval_queries.jsonl",
                 "query_expansion_audit.jsonl", "comparison_metrics.json"):
        verify(reference / name, expansion["artifacts"][name])
    _require(verified[reference / "retrieval_queries.jsonl"] == native_inputs["retrieval_queries.jsonl"],
             "Frozen question projection changed")
    tasks = Path(tasks_path or native["inputs"]["tasks"]["path"]).resolve()
    task_identity = verify(tasks)
    _require(task_identity["sha256"] == native["inputs"]["tasks"]["sha256"] == expansion["task_sha256"],
             "Frozen task annotations changed")
    summary = read_json(baseline / "extraction_summary.json")
    totals = native["manifest_totals"]
    docs = {d["doc_id"]: d for d in summary["documents"]}
    _require(len(docs) == len(summary["documents"]) == totals["documents"] and summary["failed_page_count"] == 0
             and summary["attempted_page_count"] == summary["page_record_count"] == totals["pages"],
             "Incomplete extraction cohort")
    raw_queries = read_jsonl(baseline / "retrieval_queries.jsonl")
    _require(all(set(r) == {"task_id", "doc_id", "question"} for r in raw_queries), "Retrieval query allowlist violated")
    queries = [RetrievalQuery.from_record(r) for r in raw_queries]
    ids = {q.task_id for q in queries}
    _require(len(ids) == len(queries) == totals["questions"] and ids and all(q.doc_id in docs for q in queries),
             "Frozen question/report coverage mismatch")
    original_saved = _by_task(read_jsonl(baseline / "retrieval_predictions.jsonl"), ids)
    saved = {key: _by_task(read_jsonl(reference / name), ids) for key, name in _PREDICTIONS.items()}
    saved_queries = _by_task(read_jsonl(reference / "expanded_retrieval_queries.jsonl"), ids)
    saved_audits = _by_task(read_jsonl(reference / "query_expansion_audit.jsonl"), ids)
    expanded, audits = {}, []
    for q in queries:
        eq, audit = expand_query(q)
        _require(saved_queries[q.task_id] == eq.to_dict() and saved_audits[q.task_id] == audit,
                 "Frozen query expansion/audit failed reproduction")
        expanded[q.task_id] = eq
        audits.append(audit)
    output.mkdir(parents=True, exist_ok=False)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    manifest = {"schema_version": 1, "status": "running", "run_id": run_id,
                "experiment": "N_native_text_bm25_section_context", "experimental_group": "development_pilot",
                "page_index_base": 0, "started_utc": started_utc, "code": code_provenance(root),
                "manifest_totals": totals, "baseline_run_id": native["run_id"], "baseline_manifest": native_identity,
                "expansion_reference_run_id": expansion["run_id"], "expansion_manifest": expansion_identity,
                "task_sha256": task_identity["sha256"],
                "inputs": {str(path): entry for path, entry in verified.items()},
                "configuration": {"section_policy": section_policy_record(), "expansion_policy": policy_record(),
                    "control_configuration": ref_config, "k1": config["k1"], "b": config["b"], "ks": config["ks"],
                    "primary_comparison": "section_context minus frozen question_expansion",
                    "body_index": "exact unchanged stopword index", "query_fields": ["task_id", "doc_id", "question"]},
                "timing_policy": "wall includes validation, control reproduction, all-report context construction, indexes, ranking, scoring and serialization; native extraction is prior shared ingestion",
                "initial_validation_seconds": time.perf_counter() - started}
    write_json(output / "run_manifest.json", manifest)
    try:
        predictions = {key: {} for key in (*_PREDICTIONS, "section_context")}
        contexts, seen = [], set()
        timing = {"context_build_seconds": 0.0, "original_index_seconds": 0.0, "body_index_seconds": 0.0,
                  "heading_index_seconds": 0.0, "query_seconds": {key: 0.0 for key in predictions}}
        for doc_id, group in groupby(iter_jsonl(baseline / "native_pages.jsonl"), lambda r: r["doc_id"]):
            _require(doc_id in docs and doc_id not in seen, "Native report groups must be contiguous and unique")
            seen.add(doc_id)
            records = list(group)
            _validate_pages(records, docs[doc_id], native)
            step = time.perf_counter()
            context = build_section_context([SourcePage.from_record(r) for r in records])
            timing["context_build_seconds"] += time.perf_counter() - step
            for row in context:
                row["source_document_sha256"] = docs[doc_id]["expected_sha256"]
            contexts.extend(context)
            if progress:
                progress(f"Validated and built source context: {doc_id}; {len(records)} pages")
            report_queries = [q for q in queries if q.doc_id == doc_id]
            if not report_queries:
                continue
            text = [(r["page_index"], r["search_text"]) for r in records]
            step = time.perf_counter()
            original = BM25Index(doc_id, text, k1=config["k1"], b=config["b"])
            timing["original_index_seconds"] += time.perf_counter() - step
            step = time.perf_counter()
            body = BM25Index(doc_id, text, k1=config["k1"], b=config["b"], tokenizer=tokenize_without_stopwords)
            timing["body_index_seconds"] += time.perf_counter() - step
            step = time.perf_counter()
            heading_index = BM25Index(doc_id, [(r["page_index"], " ".join(r["heading_tokens"])) for r in context],
                                      k1=config["k1"], b=config["b"], tokenizer=tokenize_without_stopwords)
            timing["heading_index_seconds"] += time.perf_counter() - step
            for q in report_queries:
                conditions = [("baseline", "N_native_text_bm25_reproduced", original, q),
                              ("stopwords", "N_native_text_bm25_stopwords", body, q),
                              ("question_expansion", "N_native_text_bm25_question_expansion", body, expanded[q.task_id]),
                              ("section_context", "N_native_text_bm25_section_context", body, expanded[q.task_id])]
                for key, condition, index, retrieval_query in conditions:
                    step = time.perf_counter()
                    ranking = (rank_with_section_context(body, heading_index, retrieval_query) if key == "section_context"
                               else index.rank(retrieval_query))
                    elapsed = time.perf_counter() - step
                    timing["query_seconds"][key] += elapsed
                    if key != "section_context":
                        _check_saved(saved[key][q.task_id], q, ranking, expansion["run_id"], condition)
                    if key == "baseline":
                        _check_saved(original_saved[q.task_id], q, ranking, native["run_id"], "N_native_text_bm25")
                    predictions[key][q.task_id] = {"schema_version": 1, "run_id": run_id, "condition": condition,
                        "task_id": q.task_id, "doc_id": doc_id, "page_index_base": 0, "page_count": len(records),
                        "status": "ok", "error": None, "no_match": ranking[0]["score"] == 0,
                        "positive_score_page_count": sum(r["score"] > 0 for r in ranking),
                        "ranked_pages": ranking, "elapsed_seconds": elapsed}
        _require(seen == set(docs) and len(contexts) == totals["pages"], "Missing full-cohort native pages")
        for key, name in {**_PREDICTIONS, "section_context": "section_predictions.jsonl"}.items():
            write_jsonl(output / name, (predictions[key][q.task_id] for q in queries))
        write_jsonl(output / "retrieval_queries.jsonl", (q.to_dict() for q in queries))
        write_jsonl(output / "expanded_retrieval_queries.jsonl", (expanded[q.task_id].to_dict() for q in queries))
        write_jsonl(output / "query_expansion_audit.jsonl", audits)
        write_jsonl(output / "section_context.jsonl", contexts)
        context_summary = {"documents": len(docs), "pages": len(contexts),
            "pages_with_heading_tokens": sum(bool(r["heading_tokens"]) for r in contexts),
            "total_heading_tokens": sum(r["heading_token_count"] for r in contexts),
            "maximum_page_heading_tokens": max(r["heading_token_count"] for r in contexts),
            "included_heading_modes": dict(Counter(h["mode"] for r in contexts for h in r["headings"] if h["included"])),
            "rejections": dict(Counter(h["rejection_reason"] for r in contexts for h in r["headings"] if not h["included"])),
            "resets": dict(Counter(reset["reason"] for r in contexts for reset in r["resets"])),
            "policy": section_policy_record(), "source_cache": native_inputs["native_pages.jsonl"]}
        write_json(output / "section_context_summary.json", context_summary)
        manifest.update({"baseline_reproduced": True, "stopword_baseline_reproduced": True,
                         "expansion_control_reproduced": True, "timings": timing})
        verify_unchanged()
        # First label parsing is after all rankings, context and query/audit artifacts are written.
        labels = load_evidence_labels(tasks)
        metrics = {key: evaluate_retrieval([predictions[key][q.task_id] for q in queries], labels, ks=tuple(config["ks"]))
                   for key in predictions}
        previous_metrics = read_json(reference / "comparison_metrics.json")
        _require(all(metrics[key] == previous_metrics[key] for key in _PREDICTIONS), "Control metrics failed reproduction")
        comparison = {**metrics, "delta_at_k": {
            k: {metric: metrics["section_context"]["at_k"][k][metric] - values[metric]
                for metric in ("macro_evidence_recall", "any_evidence_hit_rate", "all_evidence_coverage_rate")}
            for k, values in metrics["question_expansion"]["at_k"].items()},
            "delta_mrr_full_ranking": metrics["section_context"]["mrr_full_ranking"] - metrics["question_expansion"]["mrr_full_ranking"],
            "interpretation": "labeled development heading-field ablation; not answer correctness, ledger memory or held-out evaluation"}
        multi = [label for label in labels if len(set(label["evidence_pages"])) > 1]
        comparison["multi_page"] = {key: evaluate_retrieval([predictions[key][l["task_id"]] for l in multi], multi,
                                        ks=tuple(config["ks"])) for key in ("question_expansion", "section_context")} if multi else None
        verify_unchanged()
        write_json(output / "comparison_metrics.json", comparison)
        verify_unchanged()
        manifest["status"] = "complete"
        manifest["artifacts"] = {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
                                 for p in sorted(output.iterdir()) if p.is_file() and p.name != "run_manifest.json"}
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["elapsed_seconds"] = time.perf_counter() - started
        write_json(output / "run_manifest.json", manifest)
    return {"status": "complete", "run_id": run_id, "output_dir": str(output), **totals,
            "expansion_control_reproduced": True, "evaluation": "complete"}


def compare_section_context(baseline_dir, expansion_dir, output_dir, **kwargs):
    try:
        return _compare_section_context(baseline_dir, expansion_dir, output_dir, **kwargs)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Malformed section-comparison input: {exc}") from exc
