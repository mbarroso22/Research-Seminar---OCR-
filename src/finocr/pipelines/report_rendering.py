"""Source-only full-report RGB rendering; no question or evidence inputs."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import uuid
import zlib

from pypdf import PdfReader

from finocr.io import read_json, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance, load_native_documents, sha256_file


def file_identity(path):
    path = Path(path)
    return {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def safe_document_name(doc_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", doc_id)[:100] + "-" + hashlib.sha256(doc_id.encode()).hexdigest()[:12]


def png_info(path):
    with Path(path).open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Renderer output is not a PNG")
        info, saw_data = None, False
        while True:
            header = handle.read(8)
            if len(header) != 8:
                raise ValueError("PNG is incomplete")
            length, kind = struct.unpack(">I4s", header)
            crc, remaining, ihdr = zlib.crc32(kind), length, b""
            while remaining:
                block = handle.read(min(remaining, 1024 * 1024))
                if not block:
                    raise ValueError("PNG chunk is truncated")
                crc = zlib.crc32(block, crc); remaining -= len(block)
                if kind == b"IHDR": ihdr += block
            stored_crc = handle.read(4)
            if len(stored_crc) != 4 or struct.unpack(">I", stored_crc)[0] != crc:
                raise ValueError("PNG chunk checksum mismatch")
            if info is None:
                if kind != b"IHDR" or length != 13:
                    raise ValueError("PNG must begin with one IHDR")
                info = struct.unpack(">IIBB", ihdr[:10])
            elif kind == b"IHDR":
                raise ValueError("Duplicate PNG IHDR")
            if kind == b"IDAT": saw_data = True
            if kind == b"IEND":
                if length or not saw_data or handle.read(1):
                    raise ValueError("Incomplete or trailing PNG data")
                break
    width, height, depth, colour = info
    if width < 1 or height < 1 or depth != 8 or colour != 2:
        raise ValueError("Expected positive-size 8-bit RGB PNG (no grayscale/alpha conversion)")
    return {"width": width, "height": height, "colour_mode": "RGB", "bit_depth": depth}


def renderer_identity(executable):
    exe = Path(executable).resolve()
    if not exe.is_file():
        raise ValueError("Explicit pdftoppm executable does not exist")
    version = subprocess.run([str(exe), "-v"], capture_output=True, text=True, timeout=30)
    if version.returncode != 0:
        raise ValueError("pdftoppm version check failed")
    # Windows bundle DLLs matter as well as the executable. Linux fixture checks
    # record the executable; Linux system-library pinning is not a Windows setup claim.
    binaries = [exe, *sorted(exe.parent.glob("*.dll"))]
    return {"executable_path": str(exe), "version_output": (version.stdout + version.stderr).strip(),
            "binary_identities": {p.name: file_identity(p) for p in binaries}}


def render_full_reports(documents_path, output_dir, *, renderer_path, repository_root=".", pdf_dir=None,
                        native_dir=None, dpi=200, sample=False, resume=False, timeout_seconds=120,
                        expected_documents=None, expected_pages=None, progress=None):
    if type(dpi) is not int or dpi <= 0 or timeout_seconds <= 0:
        raise ValueError("Positive integer DPI and positive page timeout required")
    root, output, documents_path = (Path(p).resolve() for p in (repository_root, output_dir, documents_path))
    if (root / ".git").exists() and (root == output or root in output.parents):
        raise ValueError("Rendered cache must be outside Git")
    if output.exists() and not resume:
        raise FileExistsError("Render directory exists; use explicit --resume or choose a new directory")
    if resume and not (output / "run_manifest.json").is_file():
        raise ValueError("Resume requires the existing render manifest")
    documents = load_native_documents(documents_path, repository_root=root, pdf_dir=Path(pdf_dir) if pdf_dir else None)
    totals = {"documents": len(documents), "pages": sum(d.page_count for d in documents)}
    if ((expected_documents is not None and totals["documents"] != expected_documents)
            or (expected_pages is not None and totals["pages"] != expected_pages)):
        raise ValueError("Full document cohort/page totals do not match")
    inputs = {"document_manifest": file_identity(documents_path)}
    input_files = {"document_manifest": documents_path}
    if native_dir is not None:
        native_dir = Path(native_dir).resolve()
        if output == native_dir or native_dir in output.parents:
            raise ValueError("Keep renders outside the native run")
        native = read_json(native_dir / "run_manifest.json")
        summary_path = native_dir / "extraction_summary.json"
        if (native["status"] != "complete" or native["condition"] != "N_native_text_bm25"
                or file_identity(summary_path) != native["artifacts"][summary_path.name]
                or inputs["document_manifest"]["sha256"] != native["inputs"]["documents"]["sha256"]):
            raise ValueError("Original native run/document identity mismatch")
        reference = {d["doc_id"]: (d["expected_page_count"], d["expected_sha256"])
                     for d in read_json(summary_path)["documents"]}
        if reference != {d.doc_id: (d.page_count, d.sha256) for d in documents}:
            raise ValueError("Native/render PDF cohort, page counts or checksums differ")
        inputs.update(native_manifest=file_identity(native_dir / "run_manifest.json"),
                      native_summary=file_identity(summary_path))
        input_files.update(native_manifest=native_dir / "run_manifest.json", native_summary=summary_path)
    renderer = renderer_identity(renderer_path)
    contract = {"inputs": inputs, "renderer": renderer, "dpi": dpi, "format": "8-bit RGB PNG",
                "page_index_base": 0, "box_policy": "Poppler default MediaBox; honor PDF rotation; no crop/deskew/denoise",
                "documents": [{"doc_id": d.doc_id, "page_count": d.page_count, "pdf_sha256": d.sha256} for d in documents]}
    prior = read_json(output / "run_manifest.json") if resume else None
    if prior and prior["contract"] != contract:
        raise ValueError("Resume input/renderer/settings changed; create a new render cache")
    # Validate the entire source cohort before rendering any selected page.
    planned = []
    for doc in documents:
        if sha256_file(doc.pdf_path) != doc.sha256:
            raise ValueError(f"Source PDF checksum mismatch: {doc.doc_id}")
        reader = PdfReader(doc.pdf_path, strict=False)
        try:
            # Match native extraction: is_encrypted remains true after decryption.
            # Only an empty password is attempted; the source PDF is never rewritten.
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError(f"PDF empty password cannot decrypt this report: {doc.doc_id}")
            observed_count = len(reader.pages)
            if observed_count != doc.page_count:
                raise ValueError(f"PDF page count mismatch: {doc.doc_id}; expected {doc.page_count}, found {observed_count}")
            for page, pdf_page in enumerate(reader.pages):
                planned.append({"doc_id": doc.doc_id, "page_index": page, "page_index_base": 0,
                    "document_sha256": doc.sha256, "dpi": dpi, "pdf_rotation": int(pdf_page.rotation),
                    "media_box_points": [float(v) for v in pdf_page.mediabox],
                    "image_path": f"images/{safe_document_name(doc.doc_id)}/page_{page:05d}.png"})
        finally:
            reader.close()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "run_id": prior["run_id"] if prior else uuid.uuid4().hex,
        "status": "running", "stage": "rendering_setup", "contract": contract, "cohort_totals": totals,
        "code": code_provenance(root), "started_utc": datetime.now(timezone.utc).isoformat(),
        "sample_policy": "first, middle, last physical page in each report; source-only; not gold-selected",
        "full_report_rendering_complete": False, "attempts": (prior or {}).get("attempts", 0) + 1}
    write_json(output / "run_manifest.json", manifest)
    selected = {(d.doc_id, p) for d in documents for p in ({0, d.page_count // 2, d.page_count - 1} if sample else range(d.page_count))}
    pdfs = {d.doc_id: d.pdf_path for d in documents}
    records, started = [], time.perf_counter()
    try:
        for plan in planned:
            key = (plan["doc_id"], plan["page_index"])
            record_path = output / "records" / safe_document_name(plan["doc_id"]) / f"page_{plan['page_index']:05d}.json"
            cached = read_json(record_path) if record_path.is_file() else None
            if cached and any(cached.get(k) != value for k, value in plan.items()):
                raise ValueError("Cached render record mapping/settings changed")
            if cached and cached["status"] == "ok":
                image = output / plan["image_path"]
                if file_identity(image) != cached["image_identity"] or png_info(image) != cached["image_info"]:
                    raise ValueError("Completed cached image checksum/metadata mismatch")
                records.append(cached)
                continue
            if key not in selected:
                records.append(cached or {**plan, "status": "pending", "render_attempted": False, "error": None})
                continue
            step = time.perf_counter()
            if progress:
                progress(f"Rendering {plan['doc_id']} physical page {plan['page_index']} at {dpi} DPI")
            record = {**plan, "render_attempted": True, "status": "failed", "error": None}
            try:
                # Temporary image and atomic move prevent accepting a half-written PNG.
                target = output / plan["image_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
                    prefix = Path(temporary) / "page"
                    physical = str(plan["page_index"] + 1)  # Poppler alone uses one-based input.
                    completed = subprocess.run([str(Path(renderer_path).resolve()), "-f", physical, "-l", physical,
                        "-singlefile", "-png", "-r", str(dpi), str(pdfs[plan["doc_id"]]), str(prefix)],
                        capture_output=True, text=True, timeout=timeout_seconds)
                    if completed.returncode != 0:
                        raise RuntimeError(completed.stderr.strip() or "pdftoppm returned failure")
                    produced = prefix.with_suffix(".png")
                    record.update(image_info=png_info(produced), image_identity=file_identity(produced))
                    produced.replace(target)
                record["status"] = "ok"
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            record["elapsed_seconds"] = time.perf_counter() - step
            write_json(record_path, record)
            records.append(record)
        for doc in documents:
            if sha256_file(doc.pdf_path) != doc.sha256:
                raise ValueError("Source PDF changed during rendering")
        if any(file_identity(path) != inputs[key] for key, path in input_files.items()) or renderer_identity(renderer_path) != renderer:
            raise ValueError("Manifest or renderer changed during rendering")
        counts = dict(Counter(r["status"] for r in records))
        selected_failed = sum(r["status"] != "ok" for r in records if (r["doc_id"], r["page_index"]) in selected)
        manifest.update(status="partial" if selected_failed else "complete" if counts.get("ok", 0) == totals["pages"] else "sample_complete",
            full_report_rendering_complete=counts.get("ok", 0) == totals["pages"],
            page_record_count=len(records), status_counts=counts, selected_page_count=len(selected),
            rendered_image_bytes=sum(r.get("image_identity", {}).get("size_bytes", 0) for r in records),
            observed_bytes_per_rendered_page=(sum(r.get("image_identity", {}).get("size_bytes", 0) for r in records) / counts["ok"] if counts.get("ok") else None),
            interpretation="setup/cache coverage only; no OCR quality or retrieval result")
        manifest["report_coverage"] = {d.doc_id: {"expected_pages": d.page_count,
            "status_counts": dict(Counter(r["status"] for r in records if r["doc_id"] == d.doc_id))} for d in documents}
        write_jsonl(output / "render_pages.jsonl", records)
        manifest["render_pages_identity"] = file_identity(output / "render_pages.jsonl")
    except BaseException as exc:
        manifest.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest.update(elapsed_seconds=time.perf_counter() - started, finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "run_manifest.json", manifest)
    return {"status": manifest["status"], "output_dir": str(output), **totals,
            "status_counts": manifest["status_counts"], "full_report_rendering_complete": manifest["full_report_rendering_complete"]}
