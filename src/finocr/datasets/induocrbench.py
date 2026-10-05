"""InduOCRBench conversion placeholder.

Map each source document/page and its reference Markdown into the shared contracts.
Preserve upstream challenge/category labels in metadata for stratified analysis.
"""

from pathlib import Path

from finocr.schemas import DocumentRecord, TaskRecord


def convert_induocrbench(
    dataset_dir: str | Path,
) -> tuple[list[DocumentRecord], list[TaskRecord]]:
    raise NotImplementedError(
        "Inspect the downloaded InduOCRBench file layout, then implement a lossless mapping."
    )

