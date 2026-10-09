"""Offline reproduction/score audit only. No task labels, PDF reads or new condition.

Run with the project's installed finocr package. Review page IDs select diagnostic
output AFTER every full-report ranking has been reproduced; they never filter an
index. The original cache and experiment artifacts remain read-only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from finocr.io import read_json, read_jsonl
from finocr.pipelines.native_baseline import sha256_file
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, normalize_search_text
from finocr.retrieval.query_expansion import expand_query, policy_record
from finocr.retrieval.stopwords import STOPWORDS, STOPWORD_VERSION, tokenize_without_stopwords


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_cache(rows, manifest, summary):
    """Verify all reports, physical page IDs, text and extraction provenance."""
    docs = {r["doc_id"]: r for r in summary["documents"]}
    require(len(docs) == len(summary["documents"]) == manifest["manifest_totals"]["documents"],
            "Extracted document coverage mismatch")
    groups = defaultdict(list)
    for row in rows:
        require(row["doc_id"] in docs, "Unknown cached report")
        doc = docs[row["doc_id"]]
        require(type(row["page_index"]) is int and row["page_index"] >= 0
                and row["page_index_base"] == 0, "Invalid physical page ID")
        require(row["run_id"] == manifest["run_id"]
                and row["document_sha256"] == row["expected_document_sha256"]
                == doc["expected_sha256"] == doc["observed_sha256"] == doc["post_extraction_sha256"],
                "Cache source/run identity mismatch")
        require(row["engine"] == manifest["configuration"]["engine"]
                and row["engine_version"] == manifest["code"]["package_versions"]["pypdf"]
                and row["extraction_mode"] == manifest["configuration"]["extraction_mode"]
                and row["representation"] == "native_pdf_text", "Extraction representation mismatch")
        require(isinstance(row["raw_text"], str)
                and row["raw_character_count"] == len(row["raw_text"])
                and row["search_text"] == normalize_search_text(row["raw_text"]),
                "Cache text/normalization mismatch")
        require(row["extraction_attempted"] is True and row["error"] is None
                and row["status"] == ("ok" if row["search_text"] else "blank_native_text"),
                "Incomplete or inconsistent extraction")
        groups[row["doc_id"]].append(row)
    require(set(groups) == set(docs), "Missing cached report")
    for doc_id, records in groups.items():
        doc = docs[doc_id]
        require([r["page_index"] for r in records] == list(range(doc["expected_page_count"])),
                "Missing, duplicate or reordered physical pages")
        require(len(records) == doc["observed_page_count"] == doc["page_record_count"]
                == doc["attempted_page_count"] and doc["failed_page_count"] == 0,
                "Document page accounting mismatch")
        require(dict(Counter(r["status"] for r in records)) == doc["status_counts"]
                and [r["page_index"] for r in records if not r["search_text"]]
                == doc["blank_native_text_indices"]
                and sum(r["raw_character_count"] for r in records) == doc["native_character_count"],
                "Extraction summary mismatch")
    require(len(rows) == manifest["manifest_totals"]["pages"] == summary["page_record_count"]
            == summary["attempted_page_count"] and summary["failed_page_count"] == 0,
            "Full-cache page accounting mismatch")
    return groups


def check_ranking(actual, saved, query):
    require(saved["doc_id"] == query.doc_id and saved["page_index_base"] == 0
            and saved["page_count"] == len(actual), "Prediction report scope mismatch")
    reference = saved["ranked_pages"]
    require(len(actual) == len(reference), "Incomplete saved ranking")
    maximum = 0.0
    for left, right in zip(actual, reference):
        require(type(right["page_index"]) is int and left["page_index"] == right["page_index"],
                "Saved page order does not reproduce")
        require(math.isfinite(right["score"]) and abs(left["score"] - right["score"]) <= 1e-12,
                "Saved score does not reproduce")
        maximum = max(maximum, abs(left["score"] - right["score"]))
    return maximum


def term_breakdown(index, query, page_index, added_terms):
    require(isinstance(query, RetrievalQuery) and query.doc_id == index.doc_id,
            "Diagnostic query must use the minimal report-scoped schema")
    require(page_index in index.counts, "Unknown diagnostic page")
    terms = sorted(set(index.tokenizer(query.question)))
    length = index.lengths[page_index]
    norm = 1 - index.b + index.b * length / index.avgdl if index.avgdl else 1 - index.b
    contributions = []
    for term in terms:
        tf, df = index.counts[page_index][term], index.df[term]
        idf = math.log1p((index.n - df + .5) / (df + .5))
        score = idf * tf * (index.k1 + 1) / (tf + index.k1 * norm) if tf else 0.0
        contributions.append({"term": term, "added": term in added_terms,
                              "tf": tf, "df": df, "idf": idf, "contribution": score})
    return {"page_index": page_index, "stopword_page_length": length, "length_normalization": norm,
            "terms": contributions,
            "base_score": sum(r["contribution"] for r in contributions if not r["added"]),
            "added_score": sum(r["contribution"] for r in contributions if r["added"]),
            "expanded_score": sum(r["contribution"] for r in contributions)}


def diagnose(native_dir, expansion_dir, task_id, pages):
    native, expansion = Path(native_dir), Path(expansion_dir)
    fingerprints = {}

    def remember(path, expected=None):
        record = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        require(expected is None or record == expected, f"Artifact checksum/size mismatch: {path.name}")
        fingerprints[path] = record
        return record

    native_hash = remember(native / "run_manifest.json")
    expansion_hash = remember(expansion / "run_manifest.json")
    nm, em = read_json(native / "run_manifest.json"), read_json(expansion / "run_manifest.json")
    require(nm["status"] == em["status"] == "complete"
            and nm["condition"] == "N_native_text_bm25"
            and em["experiment"] == "N_native_text_bm25_question_expansion", "Unsupported run manifests")
    require(em["baseline_manifest_sha256"] == native_hash["sha256"]
            and em["baseline_run_id"] == nm["run_id"]
            and em["manifest_totals"] == nm["manifest_totals"], "Run lineage mismatch")
    require(em["configuration"]["expansion_policy"] == policy_record(), "Expansion policy drift")
    require(em["configuration"]["stopword_version"] == STOPWORD_VERSION
            and em["configuration"]["stopwords"] == sorted(STOPWORDS)
            and em["configuration"]["stopword_sha256"]
            == hashlib.sha256("\n".join(sorted(STOPWORDS)).encode()).hexdigest(), "Stopword policy drift")
    for key in ("k1", "b"):
        require(nm["configuration"][key] == em["configuration"][key], "BM25 configuration drift")
    for name in ("native_pages.jsonl", "extraction_summary.json"):
        remember(native / name, nm["artifacts"][name])
        require(em["inputs"][name] == nm["artifacts"][name], "Expansion cache lineage mismatch")
    names = {"original": "baseline_reproduced_predictions.jsonl",
             "stopwords": "stopword_predictions.jsonl", "expansion": "expanded_predictions.jsonl"}
    for name in (*names.values(), "retrieval_queries.jsonl", "expanded_retrieval_queries.jsonl",
                 "query_expansion_audit.jsonl", "comparison_metrics.json"):
        remember(expansion / name, em["artifacts"][name])
    groups = validate_cache(read_jsonl(native / "native_pages.jsonl"), nm,
                            read_json(native / "extraction_summary.json"))

    def by_id(name):
        rows = read_jsonl(expansion / name)
        mapping = {row["task_id"]: row for row in rows}
        require(len(mapping) == len(rows), "Duplicate task IDs")
        return mapping

    raw_queries = by_id("retrieval_queries.jsonl")
    require(len(raw_queries) == nm["manifest_totals"]["questions"], "Question coverage mismatch")
    require(all(set(r) == {"task_id", "doc_id", "question"} for r in raw_queries.values()),
            "Query file contains fields outside the retrieval allowlist")
    queries = {key: RetrievalQuery.from_record(row) for key, row in raw_queries.items()}
    predictions = {key: by_id(name) for key, name in names.items()}
    expanded, audits = by_id("expanded_retrieval_queries.jsonl"), by_id("query_expansion_audit.jsonl")
    for mapping in (*predictions.values(), expanded, audits):
        require(set(mapping) == set(queries), "Artifact task coverage mismatch")
    maximum, score_count, selected = 0.0, 0, None
    for doc_id, records in groups.items():
        text = [(r["page_index"], r["search_text"]) for r in records]
        relevant = [q for q in queries.values() if q.doc_id == doc_id]
        if not relevant:
            continue
        original = BM25Index(doc_id, text, k1=nm["configuration"]["k1"], b=nm["configuration"]["b"])
        stop = BM25Index(doc_id, text, k1=original.k1, b=original.b, tokenizer=tokenize_without_stopwords)
        for query in relevant:
            transformed, audit = expand_query(query)
            require(expanded[query.task_id] == transformed.to_dict() and audits[query.task_id] == audit,
                    "Question expansion/audit does not reproduce")
            rankings = {}
            for condition, index, q in (("original", original, query), ("stopwords", stop, query),
                                        ("expansion", stop, transformed)):
                rank = index.rank(q)
                maximum = max(maximum, check_ranking(rank, predictions[condition][q.task_id], query))
                score_count += len(rank)
                rankings[condition] = rank
            if query.task_id == task_id:
                ranks = {key: {r["page_index"]: (i + 1, r["score"]) for i, r in enumerate(value)}
                         for key, value in rankings.items()}
                details = []
                for page in pages:
                    detail = term_breakdown(stop, transformed, page, set(audit["added_terms"]))
                    require(abs(detail["base_score"] - ranks["stopwords"][page][1]) <= 1e-12
                            and abs(detail["expanded_score"] - ranks["expansion"][page][1]) <= 1e-12,
                            "Term attribution does not reproduce score")
                    detail["ranks"] = {k: v[page][0] for k, v in ranks.items()}
                    details.append(detail)
                selected = {"query": query.to_dict(), "expanded_query": transformed.to_dict(), "audit": audit,
                            "N": stop.n, "average_page_length": stop.avgdl,
                            "total_page_tokens": sum(stop.lengths.values()), "pages": details,
                            "top5": {k: v[:5] for k, v in rankings.items()}}
    require(all(q.doc_id in groups for q in queries.values()) and selected is not None,
            "Unknown query report or selected task")
    for path, expected in fingerprints.items():
        require({"sha256": sha256_file(path), "size_bytes": path.stat().st_size} == expected,
                "Input changed during diagnostic")
    return {"kind": "offline_reproduction_of_existing_run", "page_index_base": 0,
            "labels_loaded": False, "retrieval_behavior_changed": False,
            "native_run_id": nm["run_id"], "expansion_run_id": em["run_id"],
            "native_manifest": native_hash, "expansion_manifest": expansion_hash,
            "inputs": {str(p): v for p, v in fingerprints.items()}, "manifest_totals": nm["manifest_totals"],
            "reproduced_rankings": len(queries) * 3, "reproduced_page_scores": score_count,
            "maximum_absolute_score_difference": maximum, "trace": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--expansion-dir", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--pages", type=int, nargs="+", required=True, help="Offline review pages only")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = Path(__file__).resolve().parents[1], args.output.resolve()
    require(root not in output.parents and output != root, "Save diagnostic outputs outside Git")
    require(not output.exists(), "Choose a new diagnostic output file")
    result = diagnose(args.native_dir, args.expansion_dir, args.task_id, args.pages)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"kind": result["kind"], "reproduced_rankings": result["reproduced_rankings"],
                      "maximum_absolute_score_difference": result["maximum_absolute_score_difference"],
                      "output": str(output)}))


if __name__ == "__main__":
    main()
