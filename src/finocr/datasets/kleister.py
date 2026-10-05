"""Kleister Charity conversion placeholder.

Create field-extraction tasks for annotated annual income, spending, and other
released targets. Preserve the original annotation string and normalization.
"""

from pathlib import Path

from finocr.schemas import DocumentRecord, TaskRecord


def convert_kleister_charity(
    dataset_dir: str | Path,
) -> tuple[list[DocumentRecord], list[TaskRecord]]:
    raise NotImplementedError(
        "Inspect the downloaded Kleister Charity release before mapping its fields."
    )

