"""Separate fixed larger-cohort experiment; the original pilot runner is unchanged."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
import hashlib
import json
import time
import uuid

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.pipelines.native_baseline import code_provenance, load_evidence_labels
from finocr.pipelines.ocr_data import require
from finocr.pipelines.report_rendering import file_identity
from finocr.pipelines.section_comparison import _by_task, _check_saved
from finocr.pipelines.hybrid_comparison import MemorySample, paired_analysis, METHODS, CONDITIONS
from finocr.pipelines.larger_spec import SPEC
from finocr.pipelines.larger_cohort import load_inputs, study_policy, totals
from finocr.retrieval.bm25 import BM25Index
from finocr.retrieval.stopwords import tokenize_without_stopwords
from finocr.retrieval.semantic import (BgeOnnxEncoder, BATCH_SIZE, DIMENSIONS, QUERY_INSTRUCTION,
                                      THREAD_ENV, reciprocal_rank_fusion, semantic_rank, token_windows, verify_model)


def company_summary(metrics, documents):
    mapping = {d['doc_id']: d['metadata']['company'] for d in documents}
    result = {}
    for condition in CONDITIONS:
        result[condition] = {}
        for method in METHODS:
            groups = {}
            for row in metrics[condition][method]['per_question']:
                groups.setdefault(mapping[row['doc_id']], []).append(row['at_k']['5']['evidence_recall'])
            result[condition][method] = {'equal_company_recall5': sum(sum(v)/len(v) for v in groups.values()) / len(groups),
                                        'companies': {k: {'questions':len(v), 'recall5':sum(v)/len(v)} for k,v in sorted(groups.items())}}
    return result


def cluster_delta(before, after, documents):
    import numpy as np
    companies = {d['doc_id']: d['metadata']['company'] for d in documents}
    left, right = ({r['task_id']: r for r in value['per_question']} for value in (before, after))
    require(set(left) == set(right) and bool(left), 'Bootstrap paired question coverage differs')
    groups = {}
    for tid in sorted(left):
        a,b = left[tid],right[tid]
        require(a['doc_id'] == b['doc_id'], 'Bootstrap report pairing changed')
        groups.setdefault(companies[a['doc_id']], []).append(b['at_k']['5']['evidence_recall'] - a['at_k']['5']['evidence_recall'])
    names = sorted(groups)
    sums = np.array([sum(groups[k]) for k in names], dtype=np.float64)
    counts = np.array([len(groups[k]) for k in names], dtype=np.float64)
    means = sums/counts
    sample = np.random.default_rng(SPEC['bootstrap']['seed']).integers(0,len(names),size=(SPEC['bootstrap']['resamples'],len(names)))
    qdraws = sums[sample].sum(axis=1) / counts[sample].sum(axis=1)
    cdraws = means[sample].mean(axis=1)
    return {'direction':'after minus before', 'company_count':len(names), 'question_count':len(left),
            'question_weighted_delta':float(sums.sum()/counts.sum()),
            'question_weighted_ci95':[float(x) for x in np.quantile(qdraws,[.025,.975],method='linear')],
            'equal_company_delta':float(means.mean()),
            'equal_company_ci95':[float(x) for x in np.quantile(cdraws,[.025,.975],method='linear')],
            'seed':SPEC['bootstrap']['seed'], 'resamples':SPEC['bootstrap']['resamples'],
            'interpretation':'paired company-cluster percentile bootstrap; exploratory, not independent question sampling'}


def uncertainty_summary(metrics, documents):
    return {'primary':'native_vs_ocr.bm25',
            'native_vs_ocr':{m:cluster_delta(metrics['native'][m],metrics['ocr'][m],documents) for m in METHODS},
            'within_representation':{c:{m:cluster_delta(metrics[c]['bm25'],metrics[c][m],documents) for m in ('semantic','hybrid')} for c in CONDITIONS}}


def summary_report(metrics, manifest):
    lines = ['# Larger new-company exploratory comparison', '',
             'Separate fixed exploratory study; no promotion gate. Original pilot FAIL remains unchanged.', '',
             '| Text | Method | Recall@5 | Hit@5 | Complete@5 | Multi-page complete@5 |',
             '|---|---|---:|---:|---:|---:|']
    for c in CONDITIONS:
        for method in METHODS:
            r=metrics[c][method];rows=r['per_question'];multi=[x for x in rows if x['gold_page_count']>1]
            hit=sum(x['at_k']['5']['any_evidence_hit'] for x in rows)
            complete=sum(x['at_k']['5']['all_evidence_coverage'] for x in rows)
            mc=sum(x['at_k']['5']['all_evidence_coverage'] for x in multi)
            lines.append(f"| {c} | {method} | {r['at_k']['5']['macro_evidence_recall']:.6%} | {hit}/{len(rows)} | {complete}/{len(rows)} | {mc}/{len(multi)} |")
    p=metrics['uncertainty']['native_vs_ocr']['bm25'];lo,hi=p['question_weighted_ci95']
    lines += ['',f"Primary OCR minus native BM25 Recall@5: {p['question_weighted_delta']*100:.6f} percentage points; company-cluster bootstrap 95% interval [{lo*100:.6f}, {hi*100:.6f}] points.",
              '', 'All question-level gains/regressions, evidence ranks, multi-page cases, equal-company sensitivity summaries and paired intervals are retained in comparison_metrics.json.',
              'Costs are single-run descriptive measurements. No controlled speedup, energy, answer quality or population-generalization claim.', '']
    return '\n'.join(lines)


def compare_larger(freeze_dir, native_dir, reference_dir, ocr_dir, tasks_path, models_dir, output_dir, *,
                   repository_root=".", check_only=False, progress=None):
    started, cpu_started = time.perf_counter(), time.process_time()
    root, output = Path(repository_root).resolve(), Path(output_dir).resolve()
    inputs = [Path(p).resolve() for p in (native_dir, reference_dir, ocr_dir, tasks_path, models_dir, freeze_dir)]
    require(not (output == root or root in output.parents), "Hybrid output must be outside the code checkout")
    require(all(output != p and p not in output.parents and output not in p.parents for p in inputs), "Output must be separate from every saved input")
    if output.exists(): raise FileExistsError("Use a new immutable hybrid output directory; no resume or overwrite")
    output.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex, "status": "running", "stage": "input_validation",
                "experiment": SPEC["experiment"], "experimental_group": SPEC["group"],
                "policy": study_policy(), "promotion_gate": None, "page_index_base": 0, "primary_k": 5, "started_utc": datetime.now(timezone.utc).isoformat(),
                "code": code_provenance(root), "artifacts": {}, "no_ocr_or_llm_execution": True}
    identities, cost = {}, {"shared": {}, "native": {}, "ocr": {}}
    write_json(output / "run_manifest.json", manifest)
    try:
        begin = time.perf_counter()
        data = load_inputs(freeze_dir, *inputs[:4], identities)  # no model loading or labels
        cost["shared"]["source_validation_seconds"] = time.perf_counter() - begin
        manifest.update(manifest_totals=totals(), coverage={
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
            require(len(labels) == totals()["questions"], "Scoring question coverage changed")
            metrics = {c: {m: evaluate_retrieval(predictions[c][m], labels, ks=(1, 3, 5)) for m in METHODS} for c in CONDITIONS}
            metrics["paired"] = {c: {m: paired_analysis(predictions[c]["bm25"], predictions[c][m], labels) for m in ("semantic", "hybrid")} for c in CONDITIONS}
            metrics["native_vs_ocr"] = {m: paired_analysis(predictions["native"][m], predictions["ocr"][m], labels) for m in METHODS}
            metrics["promotion_gate"] = None
            metrics["uncertainty"] = uncertainty_summary(metrics, data["documents"])
            metrics["company_weighted"] = company_summary(metrics, data["documents"])
            metrics["interpretation"] = "separate larger exploratory study; known prior-company exclusions; no exhaustive exposure certification; no promotion gate, parameter sweep or answer generation"
            write_json(output / "comparison_metrics.json", metrics)
            (output / "comparison_report.md").write_text(summary_report(metrics, manifest), encoding="utf-8")
            manifest["promotion_gate"] = None
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
            "promotion_gate": None, "manifest_totals": totals()}
