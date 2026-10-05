from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from finocr.schemas import DocumentRecord, PageWindow


@dataclass(slots=True)
class ExperimentJob:
    doc_id: str
    model_id: str
    strategy: str
    start_page: int
    end_page: int
    page_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_page_windows(
    document: DocumentRecord,
    page_sizes: Iterable[int],
    *,
    windows_per_size: int,
    seed: int,
) -> list[PageWindow]:
    """Create deterministic beginning/middle/end windows for length scaling."""
    rng = random.Random(f"{seed}:{document.doc_id}")
    windows: list[PageWindow] = []
    for requested_size in page_sizes:
        size = min(requested_size, document.page_count)
        max_start = document.page_count - size
        anchors = {0, max_start, max_start // 2}
        while len(anchors) < min(windows_per_size, max_start + 1):
            anchors.add(rng.randint(0, max_start))
        for start in sorted(anchors)[:windows_per_size]:
            windows.append(PageWindow(document.doc_id, start, start + size))
    unique = {(window.start_page, window.end_page): window for window in windows}
    return list(unique.values())


def build_experiment_jobs(
    documents: list[DocumentRecord],
    model_configs: list[dict[str, object]],
    *,
    page_sizes: list[int],
    windows_per_size: int,
    seed: int,
) -> list[ExperimentJob]:
    jobs: list[ExperimentJob] = []
    for document in documents:
        windows = build_page_windows(
            document,
            page_sizes,
            windows_per_size=windows_per_size,
            seed=seed,
        )
        for model in model_configs:
            if not model.get("enabled", True):
                continue
            model_id = str(model["id"])
            for strategy in model.get("strategies", []):
                for window in windows:
                    jobs.append(
                        ExperimentJob(
                            doc_id=document.doc_id,
                            model_id=model_id,
                            strategy=str(strategy),
                            start_page=window.start_page,
                            end_page=window.end_page,
                            page_count=window.page_count,
                        )
                    )
    return jobs

