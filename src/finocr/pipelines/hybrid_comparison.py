"""Fixed BM25 / semantic / RRF comparison on the original pilot caches only."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from itertools import groupby
import json
from pathlib import Path
import threading
import time
import uuid

from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance, load_evidence_labels
from finocr.pipelines.ocr_data import coverage, full_render, inside, require, validate_text_record
from finocr.pipelines.report_ocr import validate_commit
from finocr.pipelines.report_rendering import file_identity
from finocr.pipelines.section_comparison import FROZEN_EXPANSION_SHA256, _by_task, _check_saved, _validate_pages
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery
from finocr.retrieval.query_expansion import expand_query, policy_record as expansion_policy
from finocr.retrieval.semantic import (BgeOnnxEncoder, BATCH_SIZE, DIMENSIONS, QUERY_INSTRUCTION, THREAD_ENV,
                                      policy_record, reciprocal_rank_fusion, semantic_rank, token_windows, verify_model)
from finocr.retrieval.stopwords import tokenize_without_stopwords

# Immutable source anchors: the already-inspected six-company evaluation cannot
# enter via a CLI cohort switch. Tiny offline fixtures patch these in tests only.
PILOT = {
    "native_manifest": "5e4213b5e7e65a53e01e78352abeb039c6c79eac7a55c9c0999f304d4d114497",
    "ocr_manifest": "c79e71c736ca6fe1f33d3fc7cdae039f212d01a094a209c3cd9eb17324afcf0d",
    "reference_manifest": "49b25103ac86366da493156e504ad6ca373a191301bd9425035d84978bd5b9e0",
    "tasks": "1d1bfa444a3041b3e51be9535ff276fc89fa3d7985231a0bd7f4aa6746395356",
    "totals": {"documents": 12, "pages": 2620, "questions": 24}, "ocr_device": "gpu:0",
}
METHODS, CONDITIONS = ("bm25", "semantic", "hybrid"), ("native", "ocr")


def load_inputs(native_dir, reference_dir, ocr_dir, tasks_path, identities):
    native_root, reference_root, ocr_root, tasks = map(Path, (native_dir, reference_dir, ocr_dir, tasks_path))
    def verify(path, expected=None):
        identity = file_identity(path)
        require(expected is None or identity == expected, f"Input artifact checksum changed: {path}")
        identities[path.resolve()] = identity
        return identity
    for key, path in (("native_manifest", native_root / "run_manifest.json"),
                      ("reference_manifest", reference_root / "run_manifest.json"),
                      ("ocr_manifest", ocr_root / "run_manifest.json"), ("tasks", tasks)):
        require(verify(path)["sha256"] == PILOT[key], f"Not the frozen original development pilot: {key}")
    native, reference, ocr = [read_json(p / "run_manifest.json") for p in (native_root, reference_root, ocr_root)]
    require(native["status"] == reference["status"] == ocr["status"] == "complete"
            and native["manifest_totals"] == reference["manifest_totals"] == PILOT["totals"]
            and ocr["cohort_totals"] == {"documents": PILOT["totals"]["documents"], "pages": PILOT["totals"]["pages"]}
            and reference["expansion_control_reproduced"] is True
            and ocr["full_ocr_coverage"] is True and ocr["mode"] == "full", "Incomplete original pilot controls")
    require(reference["inputs"]["native_manifest"] == verify(native_root / "run_manifest.json")
            and reference["inputs"]["ocr_manifest"] == verify(ocr_root / "run_manifest.json")
            and reference["inputs"]["tasks"] == verify(tasks), "Matched control lineage differs")
    config = reference["configuration"]
    require(expansion_policy()["sha256"] == FROZEN_EXPANSION_SHA256 and config["expansion_policy"] == expansion_policy()
            and config["k1"] == 1.2 and config["b"] == .75 and config["ks"] == [1, 3, 5], "Frozen expansion/scoring changed")
    for directory, manifest in ((native_root, native), (reference_root, reference), (ocr_root, ocr)):
        for name, identity in manifest["artifacts"].items(): verify(inside(directory.resolve(), name), identity)
    summary = read_json(native_root / "extraction_summary.json")
    docs = {d["doc_id"]: d for d in summary["documents"]}
    native_pages = read_jsonl(native_root / "native_pages.jsonl")
    seen = set()
    for doc_id, grouped in groupby(native_pages, lambda r: r["doc_id"]):
        require(doc_id in docs and doc_id not in seen, "Native report order/coverage changed")
        seen.add(doc_id); _validate_pages(list(grouped), docs[doc_id], native)
    require(seen == set(docs) and len(native_pages) == PILOT["totals"]["pages"], "Incomplete native coverage")
    contract = ocr["contract"]
    require(contract["configuration"]["device"] == PILOT["ocr_device"], "Wrong original OCR device/cache")
    render, plans, render_ids = full_render(ocr_root / "source-render", verify_images=False)
    for name, identity in render_ids.items():
        require(contract[name] == identity, "Retained rendering contract differs")
    verify(ocr_root / "source-render/run_manifest.json", render_ids["render_manifest"])
    verify(ocr_root / "source-render/render_pages.jsonl", render_ids["render_pages"])
    require(contract["render_contract"] == render["contract"], "OCR/render source contracts differ")
    require({d["doc_id"]: (d["page_count"], d["pdf_sha256"]) for d in render["contract"]["documents"]}
            == {k: (v["expected_page_count"], v["expected_sha256"]) for k, v in docs.items()}, "Native/OCR PDF identities differ")
    ocr_pages = read_jsonl(ocr_root / "ocr_pages.jsonl")
    require([(r["doc_id"], r["page_index"]) for r in ocr_pages] == [(r["doc_id"], r["page_index"]) for r in plans],
            "OCR page coverage/order differs")
    for row, plan in zip(ocr_pages, plans):
        validate_text_record(row)
        require(row["status"] in {"ok", "blank_ocr_text"} and row["page_index_base"] == 0, "Incomplete OCR page")
        path = inside(ocr_root.resolve(), row["record_path"]); verify(path, row["record_identity"])
        require(validate_commit(ocr_root, path, plan, contract, ocr["run_id"]) == row, "OCR raw/commit/aggregate differs")
        for name, identity in row["attempt_artifacts"].items(): verify(path.parent / name, identity)
    require(coverage(ocr_pages) == ocr["coverage"], "OCR coverage summary differs")
    queries = read_jsonl(reference_root / "retrieval_queries.jsonl")
    require(queries == read_jsonl(native_root / "retrieval_queries.jsonl")
            and all(set(q) == {"task_id", "doc_id", "question"} for q in queries), "Question allowlist/identity differs")
    expanded, audit = [], []
    for row in queries:
        query, record = expand_query(RetrievalQuery.from_record(row)); expanded.append(query); audit.append(record)
    require([q.to_dict() for q in expanded] == read_jsonl(reference_root / "expanded_retrieval_queries.jsonl")
            and audit == read_jsonl(reference_root / "query_expansion_audit.jsonl"), "Expansion queries/audit did not reproduce")
    ids = {q.task_id for q in expanded}
    require(len(ids) == len(expanded) == PILOT["totals"]["questions"] and all(q.doc_id in docs for q in expanded), "Question coverage differs")
    controls = {c: _by_task(read_jsonl(reference_root / f"{c}_predictions.jsonl"), ids) for c in CONDITIONS}
    return {"native": native, "reference": reference, "ocr": ocr, "render": render, "summary": summary,
            "pages": {"native": native_pages, "ocr": ocr_pages}, "queries": queries, "expanded": expanded,
            "audit": audit, "controls": controls, "tasks": tasks, "docs": docs}


def paired_analysis(before, after, labels):
    left, right = ({r["task_id"]: r for r in seq} for seq in (before, after))
    rows = []
    for label in labels:
        tid, gold = label["task_id"], set(label["evidence_pages"])
        a, b = ([r["page_index"] for r in side[tid]["ranked_pages"]] for side in (left, right))
        ah, bh = gold & set(a[:5]), gold & set(b[:5])
        rows.append({"task_id": tid, "doc_id": label["doc_id"], "gold_pages": sorted(gold),
                     "before_top5": a[:5], "after_top5": b[:5], "before_recall5": len(ah) / len(gold),
                     "after_recall5": len(bh) / len(gold), "delta_recall5": (len(bh) - len(ah)) / len(gold),
                     "before_complete5": int(ah == gold), "after_complete5": int(bh == gold),
                     "gained_evidence_pages": sorted(bh - ah), "lost_evidence_pages": sorted(ah - bh),
                     "evidence_ranks": [{"page_index": p, "before": a.index(p) + 1, "after": b.index(p) + 1} for p in sorted(gold)]})
    multi = [r for r in rows if len(r["gold_pages"]) > 1]
    return {"questions": rows, "recall5_gain_tasks": [r["task_id"] for r in rows if r["delta_recall5"] > 0],
            "recall5_regression_tasks": [r["task_id"] for r in rows if r["delta_recall5"] < 0],
            "complete5_gain_tasks": [r["task_id"] for r in rows if r["after_complete5"] > r["before_complete5"]],
            "complete5_regression_tasks": [r["task_id"] for r in rows if r["after_complete5"] < r["before_complete5"]],
            "multipage": {"question_count": len(multi), "before_complete5": sum(r["before_complete5"] for r in multi),
                          "after_complete5": sum(r["after_complete5"] for r in multi), "questions": multi}}


def development_gate(metrics):
    checks = {}
    for condition in CONDITIONS:
        b, h = (metrics[condition][m] for m in ("bm25", "hybrid"))
        complete = sum(r["at_k"]["5"]["all_evidence_coverage"] for r in h["per_question"])
        multi = [r for r in h["per_question"] if r["gold_page_count"] > 1]
        checks[condition] = {
            "recall5_strictly_improves": h["at_k"]["5"]["macro_evidence_recall"] > b["at_k"]["5"]["macro_evidence_recall"],
            "complete5_at_least_10_of_24": h["question_count"] == 24 and complete >= 10,
            "at_least_one_complete_multipage": any(r["at_k"]["5"]["all_evidence_coverage"] for r in multi),
        }
    return {"pass": all(all(v.values()) for v in checks.values()), "checks": checks,
            "policy": "fixed hybrid versus BM25; all six criteria required; semantic-only is diagnostic; no automatic tuning or promotion"}


class MemorySample:
    """Descriptive host RSS samples, not device memory, energy, or guaranteed peak."""
    def __enter__(self):
        import psutil
        self.process = psutil.Process(); self.stop_event = threading.Event()
        self.samples = [self.process.memory_info().rss]
        def sample():
            while not self.stop_event.wait(.25): self.samples.append(self.process.memory_info().rss)
        self.thread = threading.Thread(target=sample, daemon=True); self.thread.start()
        return self
    def __exit__(self, *args):
        self.stop_event.set(); self.thread.join(); self.samples.append(self.process.memory_info().rss)
    def record(self):
        return {"rss_start_bytes": self.samples[0], "rss_end_bytes": self.samples[-1],
                "sampled_max_rss_bytes": max(self.samples), "sample_interval_seconds": .25,
                "policy": "single process; sampled RSS, may miss true peak; no power/energy inference"}


def summary_report(metrics, manifest):
    lines = ["# Fixed hybrid development comparison", "", "Execution output pending independent review; original label-exposed development pilot only.", "",
             "| Text | Method | Recall@5 | Hit@5 | Complete@5 | Multi-page complete@5 |", "|---|---|---:|---:|---:|---:|"]
    for c in CONDITIONS:
        for m in METHODS:
            result = metrics[c][m]; k = result["at_k"]["5"]; rows = result["per_question"]
            multi = [r for r in rows if r["gold_page_count"] > 1]
            lines.append(f"| {c} | {m} | {k['macro_evidence_recall']:.6%} | {sum(r['at_k']['5']['any_evidence_hit'] for r in rows)}/{len(rows)} | {sum(r['at_k']['5']['all_evidence_coverage'] for r in rows)}/{len(rows)} | {sum(r['at_k']['5']['all_evidence_coverage'] for r in multi)}/{len(multi)} |")
    lines += ["", f"Development gate: **{'PASS' if metrics['development_gate']['pass'] else 'FAIL'}**. Successful execution does not imply gate success.", "",
              "All per-question changes, full evidence ranks and all five multi-page items are in comparison_metrics.json.", ""]
    for c in CONDITIONS:
        for m in ("semantic", "hybrid"):
            pair = metrics["paired"][c][m]
            lines += [f"{c}, {m} versus BM25: Recall@5 gains: {', '.join(pair['recall5_gain_tasks']) or 'none'}; regressions: {', '.join(pair['recall5_regression_tasks']) or 'none'}.",
                      f"Complete@5 gains: {', '.join(pair['complete5_gain_tasks']) or 'none'}; regressions: {', '.join(pair['complete5_regression_tasks']) or 'none'}.", ""]
    lines += ["Costs: cost_summary.json separates model initialization, shared query encoding, source tokenization/encoding, BM25 build/query, semantic ranking, RRF and validation/export wall time.",
              "OCR/native/render timings are retained historical descriptive measurements. No new OCR, controlled speedup, energy, answer quality or unseen-company generalization is measured.", ""]
    return "\n".join(lines)


def compare_hybrid(native_dir, reference_dir, ocr_dir, tasks_path, models_dir, output_dir, *,
                   repository_root=".", check_only=False, progress=None):
    started, cpu_started = time.perf_counter(), time.process_time()
    root, output = Path(repository_root).resolve(), Path(output_dir).resolve()
    inputs = [Path(p).resolve() for p in (native_dir, reference_dir, ocr_dir, tasks_path, models_dir)]
    require(not (output == root or root in output.parents), "Hybrid output must be outside the code checkout")
    require(all(output != p and p not in output.parents and output not in p.parents for p in inputs), "Output must be separate from every saved input")
    if output.exists(): raise FileExistsError("Use a new immutable hybrid output directory; no resume or overwrite")
    output.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex, "status": "running", "stage": "input_validation",
                "experiment": "original_pilot_fixed_semantic_rrf_development", "experimental_group": "development_pilot",
                "policy": policy_record(), "page_index_base": 0, "primary_k": 5, "started_utc": datetime.now(timezone.utc).isoformat(),
                "code": code_provenance(root), "artifacts": {}, "no_ocr_or_llm_execution": True}
    identities, cost = {}, {"shared": {}, "native": {}, "ocr": {}}
    write_json(output / "run_manifest.json", manifest)
    try:
        begin = time.perf_counter()
        data = load_inputs(*inputs[:4], identities)  # no model loading or labels
        cost["shared"]["source_validation_seconds"] = time.perf_counter() - begin
        manifest.update(manifest_totals=PILOT["totals"], coverage={
            "native_status_counts": dict(Counter(r["status"] for r in data["pages"]["native"])), "ocr": data["ocr"]["coverage"]},
            bm25_configuration=data["reference"]["configuration"])
        predictions = {c: {m: [] for m in METHODS} for c in CONDITIONS}
        def prediction(c, m, query, ranking, count):
            return {"schema_version": 1, "run_id": manifest["run_id"], "condition": c + "_" + m,
                    "task_id": query.task_id, "doc_id": query.doc_id, "page_count": count, "page_index_base": 0,
                    "status": "ok", "error": None, "no_match": ranking[0]["score"] == 0 if m == "bm25" else all(r.get("empty", False) for r in ranking) if m == "semantic" else False,
                    "ranked_pages": ranking}
        manifest["stage"] = "bm25_reproduction"
        for c in CONDITIONS:
            cost[c].update(bm25_build_seconds=0., bm25_query_seconds=0.)
            for doc, grouped in groupby(data["pages"][c], lambda r: r["doc_id"]):
                pages = list(grouped); begin = time.perf_counter()
                index = BM25Index(doc, [(r["page_index"], r["search_text"]) for r in pages], k1=1.2, b=.75, tokenizer=tokenize_without_stopwords)
                cost[c]["bm25_build_seconds"] += time.perf_counter() - begin
                for query in data["expanded"]:
                    if query.doc_id != doc: continue
                    begin = time.perf_counter(); ranking = index.rank(query)
                    cost[c]["bm25_query_seconds"] += time.perf_counter() - begin
                    _check_saved(data["controls"][c][query.task_id], query, ranking, data["reference"]["run_id"], c + "_expansion_v1")
                    predictions[c]["bm25"].append(prediction(c, "bm25", query, ranking, len(pages)))
            predictions[c]["bm25"].sort(key=lambda p: next(i for i, q in enumerate(data["expanded"]) if q.task_id == p["task_id"]))
            write_jsonl(output / f"{c}_bm25_predictions.jsonl", predictions[c]["bm25"])
        manifest["expansion_control_reproduced"] = {c: True for c in CONDITIONS}
        write_jsonl(output / "retrieval_queries.jsonl", data["queries"])
        write_jsonl(output / "expanded_retrieval_queries.jsonl", [q.to_dict() for q in data["expanded"]])
        write_jsonl(output / "query_expansion_audit.jsonl", data["audit"])
        cost["shared"]["input_validation_and_bm25_wall_seconds"] = time.perf_counter() - started
        if not check_only:
            # This environment belongs only to the child encoder process.
            import os
            os.environ.update(THREAD_ENV)
            import numpy as np
            manifest["stage"] = "semantic_encoding"
            for name, identity in verify_model(models_dir).items(): identities[(Path(models_dir) / name).resolve()] = identity
            with MemorySample() as memory:
                begin = time.perf_counter(); encoder = BgeOnnxEncoder(models_dir)
                cost["shared"]["encoder_initialization_seconds"] = time.perf_counter() - begin
                manifest["encoder_runtime"] = encoder.identity
                query_inputs = [{**q.to_dict(), "encoder_input": QUERY_INSTRUCTION + q.question} for q in data["expanded"]]
                write_jsonl(output / "encoder_queries.jsonl", query_inputs)
                begin = time.perf_counter(); query_ids = [encoder.token_ids(q["encoder_input"]) for q in query_inputs]
                require(all(0 < len(ids) <= 510 for ids in query_ids), "Query exceeds fixed 510-token policy; no silent truncation")
                cost["shared"]["query_tokenization_seconds"] = time.perf_counter() - begin
                begin = time.perf_counter(); query_vectors = encoder.encode_ids(query_ids)
                cost["shared"]["query_encoding_seconds"] = time.perf_counter() - begin
                np.save(output / "query_vectors.npy", query_vectors, allow_pickle=False)
                for c in CONDITIONS:
                    cost[c].update(source_tokenization_seconds=0., source_encoding_seconds=0., semantic_ranking_seconds=0.,
                                   rrf_seconds=0., windows=0, source_content_tokens=0, encoded_content_tokens=0, reports=[])
                    saved_bm25 = {p["task_id"]: p for p in predictions[c]["bm25"]}
                    for report_number, (doc, grouped) in enumerate(groupby(data["pages"][c], lambda r: r["doc_id"])):
                        pages = list(grouped); sequences, windows = [], []; begin = time.perf_counter()
                        for page in pages:
                            ids = encoder.token_ids(page["search_text"]); cost[c]["source_content_tokens"] += len(ids)
                            for w, (start, end, tokens) in enumerate(token_windows(ids)):
                                windows.append({"doc_id": doc, "page_index": page["page_index"], "window_index": w,
                                                "vector_index": len(sequences), "start_token": start, "end_token": end,
                                                "token_ids_sha256": hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()})
                                sequences.append(tokens)
                        token_seconds = time.perf_counter() - begin; cost[c]["source_tokenization_seconds"] += token_seconds
                        prefix = f"vectors/{c}_report_{report_number:02d}"
                        write_jsonl(output / (prefix + "_windows.jsonl"), windows)
                        vectors = np.empty((len(sequences), DIMENSIONS), dtype=np.float32); begin = time.perf_counter()
                        for start in range(0, len(sequences), BATCH_SIZE):
                            stop = min(start + BATCH_SIZE, len(sequences)); vectors[start:stop] = encoder.encode_ids(sequences[start:stop])
                            if progress and (start % 128 == 0 or stop == len(sequences)):
                                progress(f"{c} {doc}: encoded windows {stop}/{len(sequences)}")
                        encoding_seconds = time.perf_counter() - begin; cost[c]["source_encoding_seconds"] += encoding_seconds
                        np.save(output / (prefix + ".npy"), vectors, allow_pickle=False)
                        cost[c]["windows"] += len(windows); cost[c]["encoded_content_tokens"] += sum(map(len, sequences))
                        cost[c]["reports"].append({"doc_id": doc, "pages": len(pages), "windows": len(windows),
                                                  "tokenization_seconds": token_seconds, "encoding_seconds": encoding_seconds, "vector_path": prefix + ".npy"})
                        for qi, query in enumerate(data["expanded"]):
                            if query.doc_id != doc: continue
                            begin = time.perf_counter(); ranking = semantic_rank(query_vectors[qi], vectors, windows, len(pages))
                            cost[c]["semantic_ranking_seconds"] += time.perf_counter() - begin
                            predictions[c]["semantic"].append(prediction(c, "semantic", query, ranking, len(pages)))
                            begin = time.perf_counter(); hybrid = reciprocal_rank_fusion(saved_bm25[query.task_id]["ranked_pages"], ranking)
                            cost[c]["rrf_seconds"] += time.perf_counter() - begin
                            predictions[c]["hybrid"].append(prediction(c, "hybrid", query, hybrid, len(pages)))
                    for m in ("semantic", "hybrid"):
                        by_id = _by_task(predictions[c][m], {q.task_id for q in data["expanded"]})
                        predictions[c][m] = [by_id[q.task_id] for q in data["expanded"]]
                        write_jsonl(output / f"{c}_{m}_predictions.jsonl", predictions[c][m])
            manifest["memory"] = memory.record()
            # First label parsing occurs after ALL SIX prediction files exist.
            manifest["stage"] = "evaluation"
            begin = time.perf_counter()
            require(file_identity(Path(tasks_path)) == identities[Path(tasks_path).resolve()], "Scoring annotations changed before evaluation")
            labels = load_evidence_labels(tasks_path)
            require(len(labels) == PILOT["totals"]["questions"], "Scoring question coverage changed")
            metrics = {c: {m: evaluate_retrieval(predictions[c][m], labels, ks=(1, 3, 5)) for m in METHODS} for c in CONDITIONS}
            metrics["paired"] = {c: {m: paired_analysis(predictions[c]["bm25"], predictions[c][m], labels) for m in ("semantic", "hybrid")} for c in CONDITIONS}
            metrics["native_vs_ocr"] = {m: paired_analysis(predictions["native"][m], predictions["ocr"][m], labels) for m in METHODS}
            metrics["development_gate"] = development_gate(metrics)
            metrics["interpretation"] = "inspected development pilot; fixed single experiment, not unseen-company performance; no answer generation"
            write_json(output / "comparison_metrics.json", metrics)
            (output / "comparison_report.md").write_text(summary_report(metrics, manifest), encoding="utf-8")
            manifest["development_gate"] = metrics["development_gate"]
            cost["shared"]["evaluation_and_reporting_seconds"] = time.perf_counter() - begin
        manifest["stage"] = "preservation"
        begin = time.perf_counter()
        for path, identity in identities.items(): require(file_identity(path) == identity, f"Input changed during run: {path}")
        write_json(output / "input_preservation.json", {"all_match": True, "files": [
            {"path": str(p), **i} for p, i in sorted(identities.items(), key=lambda item: str(item[0]))]})
        cost["shared"]["preservation_validation_seconds"] = time.perf_counter() - begin
        cost["historical_preprocessing"] = {k: data["reference"][k] for k in ("prior_native_extraction_seconds", "prior_ocr_ingestion_timing", "prior_rendering_timing")}
        cost["shared"].update(total_wall_seconds=time.perf_counter() - started, total_process_cpu_seconds=time.process_time() - cpu_started)
        cost["policy"] = "fixed native-then-OCR order; shared model/query work reported once; source encoding is added preprocessing; single descriptive run, no controlled CPU/GPU speedup or energy measurement"
        write_json(output / "cost_summary.json", cost)
        manifest.update(status="inputs_verified_no_encoder" if check_only else "complete", stage="finished")
    except BaseException as exc:
        manifest.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest.update(elapsed_seconds=time.perf_counter() - started, finished_utc=datetime.now(timezone.utc).isoformat())
        manifest["artifacts"] = {p.relative_to(output).as_posix(): file_identity(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "run_manifest.json"}
        write_json(output / "run_manifest.json", manifest)
    return {"status": manifest["status"], "output_dir": str(output), "expansion_control_reproduced": manifest["expansion_control_reproduced"],
            "development_gate": manifest.get("development_gate"), "manifest_totals": PILOT["totals"]}
