from __future__ import annotations


def page_risk_score(
    *,
    model_disagreement: float,
    malformed_structure: bool,
    numeric_inconsistency: float,
    repetition_ratio: float = 0.0,
) -> float:
    """Simple preregisterable risk score; weights must be tuned only on development data."""
    components = (
        0.40 * _clip(model_disagreement)
        + 0.25 * float(malformed_structure)
        + 0.25 * _clip(numeric_inconsistency)
        + 0.10 * _clip(repetition_ratio)
    )
    return _clip(components)


def select_pages_for_review(page_scores: dict[int, float], threshold: float) -> list[int]:
    return sorted(page for page, score in page_scores.items() if score >= threshold)


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))

