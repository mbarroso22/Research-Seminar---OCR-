"""Compare the final note-format ablation to two reproduced frozen controls."""
from __future__ import annotations

from finocr.pipelines.section_comparison import _compare_section_context


def compare_note_formats(baseline_dir, expansion_dir, section_dir, output_dir, **kwargs):
    try:
        return _compare_section_context(baseline_dir, expansion_dir, output_dir,
                                        note_reference_dir=section_dir, **kwargs)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Malformed note-format comparison input: {exc}") from exc


def paired_comparisons(predictions, metrics, labels, ks):
    """Offline only: called after source contexts and all full predictions are saved."""
    result = {}
    multi_ids = {l["task_id"] for l in labels if len(set(l["evidence_pages"])) > 1}
    names = ("evidence_recall", "any_evidence_hit", "all_evidence_coverage")
    aggregate_names = ("macro_evidence_recall", "any_evidence_hit_rate", "all_evidence_coverage_rate")
    treatment = {r["task_id"]: r for r in metrics["note_formats"]["per_question"]}
    for control in ("section_context", "question_expansion"):
        previous = {r["task_id"]: r for r in metrics[control]["per_question"]}
        details = []
        for label in labels:
            task = label["task_id"]
            ranks = {key: {r["page_index"]: i for i, r in enumerate(predictions[key][task]["ranked_pages"], 1)}
                     for key in (control, "note_formats")}
            details.append({"task_id": task, "doc_id": label["doc_id"], "multi_page": task in multi_ids,
                "gold_page_ranks": [{"page_index": page, "control_rank": ranks[control][page],
                    "note_rank": ranks["note_formats"][page],
                    "rank_change": ranks["note_formats"][page] - ranks[control][page]}
                    for page in sorted(set(label["evidence_pages"]))],
                "delta_at_k": {str(k): {name: treatment[task]["at_k"][str(k)][name]
                    - previous[task]["at_k"][str(k)][name] for name in names} for k in ks},
                "delta_reciprocal_rank": treatment[task]["reciprocal_rank"] - previous[task]["reciprocal_rank"]})
        result[control] = {
            "direction": "note_formats minus control; negative rank_change means improvement",
            "delta_at_k": {str(k): {name: metrics["note_formats"]["at_k"][str(k)][name]
                - metrics[control]["at_k"][str(k)][name] for name in aggregate_names} for k in ks},
            "delta_mrr_full_ranking": metrics["note_formats"]["mrr_full_ranking"] - metrics[control]["mrr_full_ranking"],
            "paired_counts_at_k": {str(k): {name: {
                "gains": sum(r["delta_at_k"][str(k)][name] > 0 for r in details),
                "regressions": sum(r["delta_at_k"][str(k)][name] < 0 for r in details),
                "unchanged": sum(r["delta_at_k"][str(k)][name] == 0 for r in details)} for name in names} for k in ks},
            "per_question": details,
            "multi_page_question_ids": sorted(multi_ids),
            "multi_page_delta_at_k": {str(k): {name: sum(r["delta_at_k"][str(k)][field]
                for r in details if r["multi_page"]) / len(multi_ids)
                for name, field in zip(aggregate_names, names)} for k in ks} if multi_ids else None,
            "multi_page_delta_mrr": sum(r["delta_reciprocal_rank"] for r in details if r["multi_page"])
                / len(multi_ids) if multi_ids else None,
        }
    return result
