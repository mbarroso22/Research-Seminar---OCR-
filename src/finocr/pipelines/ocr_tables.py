"""Source-selected financial tables; offline approximate numeric inspection."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from finocr.io import read_json, read_jsonl, write_json
from finocr.pipelines.ocr_data import full_render, require
from finocr.pipelines.report_rendering import file_identity
from finocr.retrieval.bm25 import normalize_search_text

REPORTS = ("financebench:AMD_2015_10K", "financebench:BESTBUY_2015_10K",
           "financebench:BOEING_2015_10K", "financebench:PEPSICO_2015_10K")
TITLE = re.compile(r"^consolidated\s+(?:statements?\s+of\s+(?:operations|income|earnings|cash\s+flows|financial\s+position)|balance\s+sheets?)(?:\s*\(continued\))?$", re.I)
NUMBER = re.compile(r"\(?[+\-\u2212]?\d[\d,]*(?:\.\d+)?%?\)?")
TABLE_POLICY = {"version": "source-financial-tables-v1", "reports": list(REPORTS), "pages_per_report": 2,
    "selection": "first two physical pages with a standalone financial-statement title in the first 700 characters, a millions unit in the first 700 characters, and at least 20 numeric tokens",
    "title_pattern": TITLE.pattern, "numeric_pattern": NUMBER.pattern, "qa_annotations": "not read"}


def native_source(native_dir):
    root = Path(native_dir).resolve(); manifest = read_json(root / "run_manifest.json")
    require(manifest["status"] == "complete" and manifest["condition"] == "N_native_text_bm25", "Complete original native source cache required")
    require(file_identity(root / "native_pages.jsonl") == manifest["artifacts"]["native_pages.jsonl"], "Native page checksum mismatch")
    require(file_identity(root / "extraction_summary.json") == manifest["artifacts"]["extraction_summary.json"], "Native summary checksum mismatch")
    documents = read_json(root / "extraction_summary.json")["documents"]
    expected = [(d["doc_id"], p) for d in documents for p in range(d["expected_page_count"])]
    records = read_jsonl(root / "native_pages.jsonl")
    require([(r["doc_id"], r["page_index"]) for r in records] == expected, "Native source page accounting mismatch")
    docs = {d["doc_id"]: d for d in documents}
    for r in records:
        require(r["page_index_base"] == 0 and r["status"] in {"ok", "blank_native_text"}
                and r["document_sha256"] == docs[r["doc_id"]]["expected_sha256"]
                and r["search_text"] == normalize_search_text(r["raw_text"]), "Native source mapping/text mismatch")
    return manifest, records, docs


def select_financial_tables(native_dir, render_dir, output_path):
    output = Path(output_path)
    if output.exists(): raise FileExistsError("Use a new diagnostic selection file")
    native, records, docs = native_source(native_dir)
    render, _, identities = full_render(render_dir)
    require({d["doc_id"]: (d["page_count"], d["pdf_sha256"]) for d in render["contract"]["documents"]}
            == {k: (d["expected_page_count"], d["expected_sha256"]) for k, d in docs.items()}, "Native/render diagnostic source cohort differs")
    pages = []
    for doc_id in REPORTS:
        selected = []
        for r in records:
            if r["doc_id"] != doc_id: continue
            prefix = r["raw_text"][:700]
            heading = next((line.strip() for line in prefix.splitlines() if TITLE.fullmatch(line.strip())), None)
            numbers = NUMBER.findall(r["raw_text"])
            if heading and re.search(r"\bmillions?\b", prefix, re.I) and len(numbers) >= 20:
                selected.append({"doc_id": doc_id, "page_index": r["page_index"], "heading": heading, "numeric_token_count": len(numbers)})
            if len(selected) == 2: break
        require(len(selected) == 2, f"Two source financial tables were not found in {doc_id}; inspect source policy before changing it")
        pages.extend(selected)
    result = {"schema_version": 1, "policy": TABLE_POLICY, "pages": pages, "page_index_base": 0,
              "inputs": {**identities, "native_pages": file_identity(Path(native_dir) / "native_pages.jsonl")},
              "interpretation": "source-only setup diagnostic, not gold-selected OCR or retrieval evaluation"}
    write_json(output, result)
    return result


def review_financial_tables(native_dir, ocr_dir, selection_path, output_path):
    output = Path(output_path)
    if output.exists(): raise FileExistsError("Use a new diagnostic review file")
    _, native_rows, _ = native_source(native_dir)
    selection = read_json(selection_path); ocr_root = Path(ocr_dir)
    require(selection["inputs"]["native_pages"] == file_identity(Path(native_dir) / "native_pages.jsonl"), "Diagnostic native source changed")
    manifest = read_json(ocr_root / "run_manifest.json")
    require(file_identity(ocr_root / "ocr_pages.jsonl") == manifest["artifacts"]["ocr_pages.jsonl"], "OCR diagnostic export checksum mismatch")
    require(manifest["contract"]["render_manifest"] == selection["inputs"]["render_manifest"], "Diagnostic rendering lineage changed")
    native = {(r["doc_id"], r["page_index"]): r for r in native_rows}
    ocr = {(r["doc_id"], r["page_index"]): r for r in read_jsonl(ocr_root / "ocr_pages.jsonl")}
    details = []
    for page in selection["pages"]:
        key = page["doc_id"], page["page_index"]; before, after = native[key], ocr[key]
        require(after["status"] != "pending", "Selected table has not been attempted")
        n = Counter(NUMBER.findall(normalize_search_text(before["raw_text"])))
        o = Counter(NUMBER.findall(after["search_text"]))
        details.append({**page, "ocr_status": after["status"], "image_path": after["image_path"],
            "record_path": after["record_path"], "native_numeric_tokens": sum(n.values()), "ocr_numeric_tokens": sum(o.values()),
            "matched_numeric_tokens": sum((n & o).values()),
            "native_numeric_token_overlap": sum((n & o).values()) / sum(n.values()) if n else None,
            "native_only_examples": list((n-o).elements())[:20], "ocr_only_examples": list((o-n).elements())[:20],
            "native_sign_examples": [t for t in n if t.startswith(("(", "-"))][:15],
            "ocr_sign_examples": [t for t in o if t.startswith(("(", "-"))][:15],
            "native_years": sorted({t for t in n if re.fullmatch(r"(?:19|20)\d{2}", t)}),
            "ocr_years": sorted({t for t in o if re.fullmatch(r"(?:19|20)\d{2}", t)})})
    result = {"schema_version": 1, "pages": details,
        "inputs": {"selection": file_identity(selection_path), "ocr_manifest": file_identity(ocr_root / "run_manifest.json"),
                   "ocr_pages": file_identity(ocr_root / "ocr_pages.jsonl")},
        "interpretation": "approximate native/OCR numeric-token overlap only; not CER/WER or financial accuracy; native text is not ground truth",
        "manual_review": ["compare PNG and raw lines/boxes", "check year columns, currency/scale and decimal separators",
                          "check parentheses/minus signs and row/column associations", "do not copy native/annotation text into OCR or indexing"]}
    write_json(output, result)
    return result
