"""Source/cache validation shared by OCR ingestion and matched retrieval."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from finocr.io import read_json, read_jsonl
from finocr.pipelines.report_rendering import file_identity, png_info
from finocr.retrieval.bm25 import normalize_search_text

SOURCE_FIELDS = ("doc_id", "page_index", "page_index_base", "document_sha256", "dpi", "image_info", "image_identity")
COMPLETED = {"ok", "blank_ocr_text"}
FAILURES = {"failed", "timed_out", "interrupted"}


def require(value, message):
    if not value:
        raise ValueError(message)


def inside(root, relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute(), "Cache path must be relative")
    path = (root / relative).resolve()
    require(root in path.parents, "Cache path escapes its input/output root")
    return path


def full_render(render_dir, *, verify_images=False):
    root = Path(render_dir).resolve()
    manifest = read_json(root / "run_manifest.json")
    require(manifest["status"] == "complete" and manifest["full_report_rendering_complete"] is True,
            "A complete full-report rendering cache is required")
    require(file_identity(root / "render_pages.jsonl") == manifest["render_pages_identity"], "Render page checksum mismatch")
    contract = manifest["contract"]
    require(contract["page_index_base"] == 0 and contract["format"] == "8-bit RGB PNG" and contract["dpi"] == 200,
            "This OCR condition requires the reviewed zero-based 200-DPI RGB rendering")
    docs = {d["doc_id"]: d for d in contract["documents"]}
    require(len(docs) == len(contract["documents"]) and all(type(d["page_count"]) is int and d["page_count"] > 0 for d in docs.values()),
            "Invalid/duplicate rendering report cohort")
    expected = [(d["doc_id"], p) for d in contract["documents"] for p in range(d["page_count"])]
    rows = read_jsonl(root / "render_pages.jsonl")
    require([(r["doc_id"], r["page_index"]) for r in rows] == expected, "Incomplete/reordered/duplicate rendering pages")
    require(manifest["cohort_totals"] == {"documents": len(docs), "pages": len(expected)}
            and manifest["page_record_count"] == len(rows) and manifest["status_counts"] == {"ok": len(rows)},
            "Rendering coverage declaration mismatch")
    projected, paths = [], set()
    for row in rows:
        doc = docs[row["doc_id"]]
        require(type(row["page_index"]) is int and row["page_index_base"] == 0 and row["status"] == "ok"
                and row["document_sha256"] == doc["pdf_sha256"] and row["dpi"] == contract["dpi"], "Rendering source identity mismatch")
        image = inside(root, row["image_path"])
        require(image not in paths, "Two source pages share an image path")
        paths.add(image)
        projected.append({**{k: row[k] for k in SOURCE_FIELDS}, "image_path": row["image_path"]})
        if verify_images:
            verify_image(root, projected[-1])
    return manifest, projected, {"render_manifest": file_identity(root / "run_manifest.json"),
                                 "render_pages": file_identity(root / "render_pages.jsonl")}


def verify_image(root, row):
    image = inside(root, row["image_path"])
    require(file_identity(image) == row["image_identity"] and png_info(image) == row["image_info"],
            f"Rendering image checksum/geometry mismatch: {row['doc_id']}/{row['page_index']}")
    return image


def coverage(rows):
    reports = {}
    for row in rows:
        counts = reports.setdefault(row["doc_id"], Counter())
        counts[row["status"]] += 1
    def summarize(counts):
        return {"expected_pages": sum(counts.values()), "status_counts": dict(counts),
                "nonempty_pages": counts["ok"], "blank_pages": counts["blank_ocr_text"],
                "completed_engine_pages": sum(counts[s] for s in COMPLETED),
                "failure_pages": sum(counts[s] for s in FAILURES), "pending_pages": counts["pending"]}
    total = Counter(r["status"] for r in rows)
    return {**summarize(total), "documents": len(reports),
            "reports": {doc: summarize(counts) for doc, counts in reports.items()}}


def validate_text_record(row):
    require(row["status"] in COMPLETED | FAILURES | {"pending"}, "Unknown OCR page status")
    require(isinstance(row["raw_text"], str) and row["search_text"] == normalize_search_text(row["raw_text"])
            and row["raw_character_count"] == len(row["raw_text"]), "OCR normalization/character count mismatch")
    require((row["status"] == "ok") == bool(row["search_text"]), "OCR text/status mismatch")
    if row["status"] not in COMPLETED:
        require(not row["raw_text"] and not row["lines"], "Failed/pending OCR text must not enter retrieval")
