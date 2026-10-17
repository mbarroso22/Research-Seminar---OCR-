"""Matched frozen expansion-v1 retrieval: only page representation changes."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from itertools import groupby
from pathlib import Path
import time
import uuid

from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance, load_evidence_labels
from finocr.pipelines.ocr_data import COMPLETED, coverage, full_render, inside, require, validate_text_record
from finocr.pipelines.report_ocr import validate_commit
from finocr.pipelines.report_rendering import file_identity
from finocr.pipelines.section_comparison import FROZEN_EXPANSION_SHA256, _by_task, _check_saved, _validate_pages
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, TOKENIZER_VERSION, TOKEN_PATTERN
from finocr.retrieval.query_expansion import expand_query, policy_record
from finocr.retrieval.stopwords import STOPWORDS, STOPWORD_VERSION, tokenize_without_stopwords


def comparison_report(metrics, manifest):
    lines = ["# Matched native/OCR execution summary", "", "Execution output awaiting independent artifact review.", "",
             "Primary budget: five pages per question; frozen expansion v1, full within-report candidates.", "",
             "| Condition | Recall@5 | Hit@5 | Complete@5 | No-match questions |", "|---|---:|---:|---:|---:|"]
    for condition in ("native", "ocr"):
        m = metrics[condition]; k = m["at_k"]["5"]; count = m["question_count"]
        lines.append(f"| {condition} | {k['macro_evidence_recall']:.6%} | {round(k['any_evidence_hit_rate']*count)}/{count} | {round(k['all_evidence_coverage_rate']*count)}/{count} | {m['no_match_question_count']} |")
    c = manifest["coverage"]; p = metrics["paired"]; multi = p["multipage"]
    lines += ["", f"Coverage: {c['documents']} reports / {c['expected_pages']} page records; {c['nonempty_pages']} nonempty, {c['blank_pages']} blank, {c['failure_pages']} failed, {c['pending_pages']} pending.",
        f"Recall@5 gains: {', '.join(p['recall5_gain_tasks']) or 'none'}. Regressions: {', '.join(p['recall5_regression_tasks']) or 'none'}.",
        f"Multi-page complete@5: native {multi['native_complete5_count']}/{multi['question_count']}; OCR {multi['ocr_complete5_count']}/{multi['question_count']}.", "",
        "| Multi-page task | Native recall@5 | OCR recall@5 | Native complete | OCR complete |", "|---|---:|---:|---:|---:|"]
    for r in multi["questions"]:
        lines.append(f"| {r['task_id']} | {r['native_recall5']:.6f} | {r['ocr_recall5']:.6f} | {r['native_complete5']} | {r['ocr_complete5']} |")
    lines += ["", "Detailed evidence ranks, gained/lost pages and extraction statuses are in comparison_metrics.json.", "",
        "Timing and ingestion history are in run_manifest.json. OCR timing includes diagnostics and retries; rendering wall time is its last retained invocation. Index/query runs have fixed native-then-OCR order.",
        "These descriptive timings are not repeated latency or energy measurements. Blank and failed pages remain zero-text candidates; zero-score ties can hit evidence by chance.",
        "No answer correctness, CER/WER, or held-out generalization is measured.", ""]
    return "\n".join(lines)


def paired_changes(native, ocr, labels, ocr_pages):
    before = {p["task_id"]: p for p in native}; after = {p["task_id"]: p for p in ocr}
    pages = {(r["doc_id"], r["page_index"]): r for r in ocr_pages}
    changes = []
    for label in labels:
        task = label["task_id"]; gold = sorted(set(label["evidence_pages"]))
        n = [r["page_index"] for r in before[task]["ranked_pages"]]
        o = [r["page_index"] for r in after[task]["ranked_pages"]]
        n_hits, o_hits = set(n[:5]) & set(gold), set(o[:5]) & set(gold)
        changes.append({"task_id": task, "doc_id": label["doc_id"], "gold_page_count": len(gold),
            "native_top5": n[:5], "ocr_top5": o[:5], "native_recall5": len(n_hits)/len(gold),
            "ocr_recall5": len(o_hits)/len(gold), "delta_recall5": (len(o_hits)-len(n_hits))/len(gold),
            "native_complete5": int(len(n_hits) == len(gold)), "ocr_complete5": int(len(o_hits) == len(gold)),
            "gained_evidence_pages": sorted(o_hits-n_hits), "lost_evidence_pages": sorted(n_hits-o_hits),
            "evidence_ranks": [{"page_index": p, "native_rank": n.index(p)+1, "ocr_rank": o.index(p)+1,
                                "ocr_status": pages[label["doc_id"], p]["status"]} for p in gold]})
    multi = [r for r in changes if r["gold_page_count"] > 1]
    return {"questions": changes, "recall5_gain_tasks": [r["task_id"] for r in changes if r["delta_recall5"] > 0],
        "recall5_regression_tasks": [r["task_id"] for r in changes if r["delta_recall5"] < 0],
        "unchanged_recall5_count": sum(r["delta_recall5"] == 0 for r in changes),
        "multipage": {"question_count": len(multi), "native_complete5_count": sum(r["native_complete5"] for r in multi),
                      "ocr_complete5_count": sum(r["ocr_complete5"] for r in multi), "questions": multi}}


def compare_native_ocr(native_dir, expansion_dir, ocr_dir, output_dir, *, tasks_path=None, repository_root=".", progress=None):
    started = time.perf_counter(); root = Path(repository_root).resolve()
    native_root, expansion_root, ocr_root, output = (Path(p).resolve() for p in (native_dir, expansion_dir, ocr_dir, output_dir))
    require(not (root / ".git").exists() or not (output == root or root in output.parents), "Comparison output must be outside Git")
    require(all(output != p and p not in output.parents and output not in p.parents for p in (native_root, expansion_root, ocr_root)),
            "Comparison output must be separate from saved input runs")
    if output.exists(): raise FileExistsError("Use a new immutable native/OCR comparison directory")
    identities = {}
    def verify(path, expected=None):
        identity = file_identity(path)
        require(expected is None or identity == expected, f"Input artifact checksum changed: {path}")
        identities[Path(path)] = identity
        return identity
    native_identity = verify(native_root / "run_manifest.json")
    expansion_identity = verify(expansion_root / "run_manifest.json")
    ocr_identity = verify(ocr_root / "run_manifest.json")
    native, expansion, ocr = (read_json(p / "run_manifest.json") for p in (native_root, expansion_root, ocr_root))
    config, ref_config = native["configuration"], expansion["configuration"]
    require(native["status"] == "complete" and native["condition"] == "N_native_text_bm25"
            and native["page_index_base"] == 0 and config["full_ranking"] is True
            and config["tokenizer_version"] == TOKENIZER_VERSION and config["token_pattern"] == TOKEN_PATTERN
            and config["k1"] == 1.2 and config["b"] == .75 and config["ks"] == [1, 3, 5]
            and config["query_fields"] == ["task_id", "doc_id", "question"]
            and config["candidate_policy"] == "all physical page indices; empty/failed page text is empty"
            and config["tie_policy"] == "score descending, zero-based page_index ascending; zero ties retained", "Unsupported frozen native configuration")
    require(expansion["status"] == "complete" and expansion["experiment"] == "N_native_text_bm25_question_expansion"
            and expansion["baseline_reproduced"] is True and expansion["stopword_baseline_reproduced"] is True
            and expansion["baseline_run_id"] == native["run_id"] and expansion["baseline_manifest_sha256"] == native_identity["sha256"]
            and expansion["manifest_totals"] == native["manifest_totals"] and expansion["page_index_base"] == 0,
            "Expansion v1 reference/native lineage mismatch")
    require(policy_record()["sha256"] == FROZEN_EXPANSION_SHA256 and ref_config["expansion_policy"] == policy_record()
            and ref_config["query_expansion"] is True and ref_config["stemming"] is False and ref_config["year_normalization"] == "unchanged"
            and ref_config["stopword_version"] == STOPWORD_VERSION and ref_config["stopwords"] == sorted(STOPWORDS)
            and ref_config["stopword_sha256"] == hashlib.sha256("\n".join(sorted(STOPWORDS)).encode()).hexdigest()
            and ref_config["page_text_transformation"] == "unchanged from stopword baseline"
            and all(ref_config[k] == config[k] for k in ("k1", "b", "ks", "query_fields", "candidate_policy", "tie_policy")),
            "Frozen expansion scoring/tokenization/policy changed")
    native_inputs = {name: verify(native_root / name, native["artifacts"][name]) for name in
                     ("native_pages.jsonl", "extraction_summary.json", "retrieval_queries.jsonl", "retrieval_predictions.jsonl")}
    require(expansion["inputs"] == native_inputs, "Expansion reference cache identity mismatch")
    for name in ("expanded_predictions.jsonl", "expanded_retrieval_queries.jsonl", "query_expansion_audit.jsonl", "retrieval_queries.jsonl"):
        verify(expansion_root / name, expansion["artifacts"][name])
    require(identities[expansion_root / "retrieval_queries.jsonl"] == native_inputs["retrieval_queries.jsonl"], "Original questions changed")
    tasks = Path(tasks_path or native["inputs"]["tasks"]["path"]).resolve()
    task_identity = verify(tasks)
    require(task_identity["sha256"] == native["inputs"]["tasks"]["sha256"] == expansion["task_sha256"], "Frozen scoring annotations changed")
    for name, identity in ocr["artifacts"].items(): verify(inside(ocr_root, name), identity)
    require(ocr["stage"] == "full_report_ocr" and ocr["mode"] == "full" and ocr["status"] in {"complete", "partial"},
            "Finalize full-report OCR before retrieval; diagnostic/paused/interrupted caches cannot be compared")
    contract = ocr["contract"]; render_contract = contract["render_contract"]
    from finocr.pipelines.ocr_device import device_condition
    device = contract["configuration"]["device"]
    configuration, pins = device_condition(device)
    require(contract["configuration"] == configuration and contract["package_pins"] == pins,
            "OCR condition differs from the frozen device settings")
    require(render_contract["inputs"]["native_manifest"] == native_identity
            and render_contract["inputs"]["native_summary"] == native_inputs["extraction_summary.json"]
            and render_contract["inputs"]["document_manifest"]["sha256"] == native["inputs"]["documents"]["sha256"], "OCR/native source lineage differs")
    summary = read_json(native_root / "extraction_summary.json"); docs = {d["doc_id"]: d for d in summary["documents"]}
    require(len(docs) == native["manifest_totals"]["documents"] and ocr["cohort_totals"] == {"documents": len(docs), "pages": native["manifest_totals"]["pages"]}
            and {d["doc_id"]: (d["page_count"], d["pdf_sha256"]) for d in render_contract["documents"]}
            == {k: (d["expected_page_count"], d["expected_sha256"]) for k, d in docs.items()}, "Matched full-report page cohort differs")
    rows = read_jsonl(ocr_root / "ocr_pages.jsonl")
    render_manifest, rendered_rows, render_identities = full_render(ocr_root / "source-render")
    require(all(contract[k] == v for k, v in render_identities.items()), "OCR retained rendering snapshot differs")
    rendered = {(r["doc_id"], r["page_index"]): r for r in rendered_rows}
    expected = [(d["doc_id"], p) for d in render_contract["documents"] for p in range(d["page_count"])]
    require([(r["doc_id"], r["page_index"]) for r in rows] == expected, "OCR export omits/reorders source candidates")
    for row in rows:
        validate_text_record(row)
        require(row["status"] != "pending" and row["page_index_base"] == 0
                and row["document_sha256"] == docs[row["doc_id"]]["expected_sha256"], "Unattempted/unmapped OCR candidates")
        path = inside(ocr_root, row["record_path"]); verify(path, row["record_identity"])
        # Source/image identities are bound by the rendering contract and immutable commits.
        validated = validate_commit(ocr_root, path, rendered[row["doc_id"], row["page_index"]], contract, ocr["run_id"])
        require(validated == row, "OCR aggregate differs from its committed raw output")
        for name, identity in row["attempt_artifacts"].items(): verify(path.parent / name, identity)
    require(coverage(rows) == ocr["coverage"] and ocr["full_ocr_coverage"] == all(r["status"] in COMPLETED for r in rows), "OCR coverage declaration differs from records")
    raw_queries = read_jsonl(native_root / "retrieval_queries.jsonl")
    require(all(set(r) == {"task_id", "doc_id", "question"} for r in raw_queries), "Query allowlist violated")
    queries = [RetrievalQuery.from_record(r) for r in raw_queries]; ids = {q.task_id for q in queries}
    require(len(ids) == len(queries) == native["manifest_totals"]["questions"] and all(q.doc_id in docs for q in queries), "Question/report cohort changed")
    saved = _by_task(read_jsonl(expansion_root / "expanded_predictions.jsonl"), ids)
    saved_queries = _by_task(read_jsonl(expansion_root / "expanded_retrieval_queries.jsonl"), ids)
    saved_audit = _by_task(read_jsonl(expansion_root / "query_expansion_audit.jsonl"), ids)
    transformed, audit = [], []
    for query in queries:
        expanded, record = expand_query(query)
        require(expanded.to_dict() == saved_queries[query.task_id] and record == saved_audit[query.task_id], "Frozen expansion query/audit did not reproduce")
        transformed.append(expanded); audit.append(record)
    native_pages = read_jsonl(native_root / "native_pages.jsonl")
    seen = set()
    for doc_id, grouped in groupby(native_pages, lambda r: r["doc_id"]):
        require(doc_id in docs and doc_id not in seen, "Native report groups changed")
        seen.add(doc_id); _validate_pages(list(grouped), docs[doc_id], native)
    require(seen == set(docs) and len(native_pages) == native["manifest_totals"]["pages"], "Native full-report coverage changed")
    output.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex, "status": "running", "stage": "matched_native_ocr_retrieval",
        "experimental_group": "development_pilot", "page_index_base": 0, "code": code_provenance(root),
        "primary_k": 5, "configuration": ref_config, "ocr_device": device, "ocr_package_pins": pins,
        "manifest_totals": native["manifest_totals"],
        "inputs": {"native_manifest": native_identity, "expansion_manifest": expansion_identity, "ocr_manifest": ocr_identity,
                   "tasks": task_identity}, "coverage": ocr["coverage"], "started_utc": datetime.now(timezone.utc).isoformat(),
        "timing_policy": "native then OCR, fixed order; descriptive build/query/ingestion logs; no repeated latency or energy benchmark"}
    write_json(output / "run_manifest.json", manifest)
    try:
        predictions = {"native": [], "ocr": []}; index_stats = []; timing = {"native": 0.0, "ocr": 0.0}
        indexing_started = time.perf_counter()
        for condition, pages in (("native", native_pages), ("ocr", rows)):
            for doc_id, grouped in groupby(pages, lambda r: r["doc_id"]):
                report = list(grouped); index_start = time.perf_counter()
                index = BM25Index(doc_id, [(r["page_index"], r["search_text"]) for r in report], k1=1.2, b=.75,
                                  tokenizer=tokenize_without_stopwords)
                index_seconds = time.perf_counter()-index_start; timing[condition] += index_seconds
                index_stats.append({"condition": condition, "doc_id": doc_id, "page_count": index.n,
                                    "average_page_tokens": index.avgdl, "index_seconds": index_seconds})
                if progress: progress(f"Indexed all {index.n} {condition} pages in {doc_id}")
                failures = sum(r["status"] not in (COMPLETED if condition == "ocr" else {"ok", "blank_native_text"}) for r in report)
                for query in transformed:
                    if query.doc_id != doc_id: continue
                    query_start = time.perf_counter(); ranking = index.rank(query); query_seconds = time.perf_counter()-query_start
                    if condition == "native":
                        _check_saved(saved[query.task_id], query, ranking, expansion["run_id"], "N_native_text_bm25_question_expansion")
                    predictions[condition].append({"schema_version": 1, "run_id": manifest["run_id"], "condition": condition+"_expansion_v1",
                        "task_id": query.task_id, "doc_id": doc_id, "page_count": len(report), "page_index_base": 0,
                        "status": "partial_extraction" if failures else "ok", "error": None,
                        "no_match": ranking[0]["score"] == 0, "positive_score_page_count": sum(r["score"] > 0 for r in ranking),
                        "ranked_pages": ranking, "elapsed_seconds": query_seconds})
        for condition in predictions:
            by_id = _by_task(predictions[condition], ids)
            predictions[condition] = [by_id[q.task_id] for q in queries]
            write_jsonl(output / f"{condition}_predictions.jsonl", predictions[condition])
        write_jsonl(output / "retrieval_queries.jsonl", raw_queries)
        write_jsonl(output / "expanded_retrieval_queries.jsonl", [q.to_dict() for q in transformed])
        write_jsonl(output / "query_expansion_audit.jsonl", audit)
        write_jsonl(output / "index_stats.jsonl", index_stats)
        manifest["expansion_control_reproduced"] = True
        # First annotation parsing: both complete rankings already exist on disk.
        verify(tasks, task_identity)
        labels = load_evidence_labels(tasks)
        n_metrics = evaluate_retrieval(predictions["native"], labels, ks=(1, 3, 5))
        o_metrics = evaluate_retrieval(predictions["ocr"], labels, ks=(1, 3, 5))
        changes = paired_changes(predictions["native"], predictions["ocr"], labels, rows)
        metrics = {"primary_k": 5, "native": n_metrics, "ocr": o_metrics,
            "delta_at_k": {k: {metric: o_metrics["at_k"][k][metric]-value[metric] for metric in
                ("macro_evidence_recall", "any_evidence_hit_rate", "all_evidence_coverage_rate")} for k, value in n_metrics["at_k"].items()},
            "paired": changes, "ocr_failure_inclusive": bool(ocr["coverage"]["failure_pages"]),
            "interpretation": "matched input-representation comparison on the label-exposed development pilot; not answer correctness, OCR transcription accuracy or held-out generalization"}
        write_json(output / "comparison_metrics.json", metrics)
        manifest.update(index_seconds=timing, query_seconds={c: sum(p["elapsed_seconds"] for p in ps) for c, ps in predictions.items()},
                        indexing_and_ranking_seconds=time.perf_counter()-indexing_started,
                        prior_ocr_ingestion_timing=ocr["timing"], prior_native_extraction_seconds=summary["elapsed_seconds"],
                        prior_rendering_timing={"last_invocation_seconds": render_manifest["elapsed_seconds"],
                            "attempts": render_manifest["attempts"],
                            "policy": "render manifest retains last invocation wall time; not cumulative rendering cost across resumes"},
                        prior_rendering_dpi=render_contract["dpi"], status="complete")
        (output / "comparison_report.md").write_text(comparison_report(metrics, manifest), encoding="utf-8")
        for path, identity in identities.items(): require(file_identity(path) == identity, f"Input changed during comparison: {path}")
        manifest["artifacts"] = {p.name: file_identity(p) for p in output.iterdir() if p.is_file() and p.name != "run_manifest.json"}
    except BaseException as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest.update(elapsed_seconds=time.perf_counter()-started, finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "run_manifest.json", manifest)
    return {"status": "complete", "output_dir": str(output), "expansion_control_reproduced": True,
            "documents": len(docs), "pages": len(rows), "questions": len(queries), "primary_k": 5,
            "ocr_failure_pages": ocr["coverage"]["failure_pages"]}
