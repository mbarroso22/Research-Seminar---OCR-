from __future__ import annotations

from typing import Any, Iterable


def evaluate_retrieval(
    predictions: Iterable[dict[str, Any]], labels: Iterable[dict[str, Any]],
    *, ks: tuple[int, ...] = (1, 3, 5),
) -> dict[str, Any]:
    """Macro metrics over every question, including failed retrievals (zero hits).

    Gold evidence is a set. Duplicate/out-of-range candidates and missing/extra
    predictions are rejected rather than silently changing ranks/denominators.
    Zero-score ties count under the declared baseline policy and are disclosed.
    """
    if not ks or any(type(k) is not int or k <= 0 for k in ks) or len(set(ks)) != len(ks):
        raise ValueError("k values must be distinct positive integers")
    by_id = {}
    for row in predictions:
        if row["task_id"] in by_id:
            raise ValueError("Duplicate prediction task_id")
        by_id[row["task_id"]] = row
    details = []
    seen = set()
    for label in labels:
        task_id = label["task_id"]
        if task_id in seen:
            raise ValueError("Duplicate label task_id")
        seen.add(task_id)
        prediction = by_id.get(task_id)
        if prediction is None or prediction["doc_id"] != label["doc_id"]:
            raise ValueError(f"Missing or wrong-report prediction: {task_id}")
        page_count = prediction["page_count"]
        if type(page_count) is not int or page_count <= 0:
            raise ValueError(f"Invalid prediction page_count: {task_id}")
        if prediction.get("page_index_base", 0) != 0:
            raise ValueError(f"Predictions must use zero-based PDF indices: {task_id}")
        if prediction["status"] not in {"ok", "partial_extraction", "document_failed"}:
            raise ValueError(f"Unknown prediction status: {task_id}")
        if type(prediction["no_match"]) is not bool:
            raise ValueError(f"Invalid no_match flag: {task_id}")
        evidence = label.get("evidence_pages")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"Empty or malformed evidence: {task_id}")
        if any(type(page) is not int or not 0 <= page < page_count for page in evidence):
            raise ValueError(f"Out-of-range evidence: {task_id}")
        gold = set(evidence)
        ranking = [row["page_index"] for row in prediction["ranked_pages"]]
        if len(set(ranking)) != len(ranking):
            raise ValueError(f"Duplicate ranked pages: {task_id}")
        if any(type(page) is not int or not 0 <= page < page_count for page in ranking):
            raise ValueError(f"Out-of-range ranked pages: {task_id}")
        if prediction["status"] == "document_failed":
            if ranking:
                raise ValueError(f"Failed report cannot have ranked pages: {task_id}")
        elif len(ranking) != page_count:
            raise ValueError(f"Full ranking must include every report page: {task_id}")
        first = next((rank for rank, page in enumerate(ranking, 1) if page in gold), None)
        at_k = {}
        for k in sorted(ks):
            hits = len(gold.intersection(ranking[:k]))
            at_k[str(k)] = {
                "evidence_recall": hits / len(gold), "any_evidence_hit": int(hits > 0),
                "all_evidence_coverage": int(hits == len(gold)), "evidence_pages_retrieved": hits,
            }
        details.append({
            "task_id": task_id, "doc_id": label["doc_id"],
            "status": prediction["status"], "no_match": prediction["no_match"],
            "gold_page_count": len(gold), "at_k": at_k,
            "reciprocal_rank": 1 / first if first else 0.0,
        })
    if not details or set(by_id) != seen:
        raise ValueError("Labels must be nonempty and match predictions exactly")
    count = len(details)
    aggregates = {}
    for k in sorted(ks):
        aggregates[str(k)] = {
            "macro_evidence_recall": sum(row["at_k"][str(k)]["evidence_recall"] for row in details) / count,
            "any_evidence_hit_rate": sum(row["at_k"][str(k)]["any_evidence_hit"] for row in details) / count,
            "all_evidence_coverage_rate": sum(row["at_k"][str(k)]["all_evidence_coverage"] for row in details) / count,
            "question_count": count,
        }
    return {
        "schema_version": 1, "question_count": count, "at_k": aggregates,
        "mrr_full_ranking": sum(row["reciprocal_rank"] for row in details) / count,
        "no_match_question_count": sum(row["no_match"] for row in details),
        "failed_question_count": sum(row["status"] == "document_failed" for row in details),
        "partial_extraction_question_count": sum(row["status"] == "partial_extraction" for row in details),
        "zero_score_policy": "retain ties by ascending zero-based page_index; ties may hit gold by chance",
        "denominator_policy": "all labeled questions, including document failures and no-match queries",
        "per_question": details,
    }
