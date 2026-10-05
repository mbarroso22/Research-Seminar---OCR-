from __future__ import annotations

import math
import re


def normalized_edit_similarity(reference: str, prediction: str) -> float:
    """Return 1 - normalized Levenshtein distance."""
    reference = _normalize_text(reference)
    prediction = _normalize_text(prediction)
    denominator = max(len(reference), len(prediction), 1)
    return 1.0 - _levenshtein(reference, prediction) / denominator


def recall_at_k(relevant_pages: set[int], ranked_pages: list[int], k: int) -> float:
    if not relevant_pages:
        return 1.0
    return len(relevant_pages.intersection(ranked_pages[:k])) / len(relevant_pages)


def reciprocal_rank(relevant_pages: set[int], ranked_pages: list[int]) -> float:
    for rank, page in enumerate(ranked_pages, start=1):
        if page in relevant_pages:
            return 1.0 / rank
    return 0.0


def evidence_page_f1(relevant_pages: set[int], predicted_pages: set[int]) -> float:
    if not relevant_pages and not predicted_pages:
        return 1.0
    if not relevant_pages or not predicted_pages:
        return 0.0
    overlap = len(relevant_pages.intersection(predicted_pages))
    precision = overlap / len(predicted_pages)
    recall = overlap / len(relevant_pages)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def numeric_match(reference: str | float, prediction: str | float, tolerance: float) -> bool:
    expected = _parse_number(reference)
    observed = _parse_number(prediction)
    if expected is None or observed is None:
        return False
    return math.isclose(expected, observed, rel_tol=tolerance, abs_tol=tolerance)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _parse_number(value: str | float) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    match = re.search(r"[-+]?\(?\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*\)?", value)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    matched = match.group(0)
    is_negative = matched.lstrip().startswith("-") or ("(" in matched and ")" in matched)
    return -number if is_negative else number


def _levenshtein(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]
