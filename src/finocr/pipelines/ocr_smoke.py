"""One-page setup smoke; subprocess deadline; no QA/evaluation inputs."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import math
from pathlib import Path
import subprocess
import struct
import sys
import time
import uuid

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance
from finocr.pipelines.report_rendering import file_identity, png_info
from finocr.retrieval.bm25 import normalize_search_text


MODEL_NAMES = ("PP-OCRv5_mobile_det", "en_PP-OCRv5_mobile_rec")
PACKAGE_PINS = {"paddlepaddle": "3.3.0", "paddleocr": "3.3.2", "paddlex": "3.3.10"}
OCR_CONFIG = {"device": "cpu", "ocr_version": "PP-OCRv5", "lang": "en",
    "use_doc_orientation_classify": False, "use_doc_unwarping": False, "use_textline_orientation": False,
    "enable_hpi": False, "use_tensorrt": False, "precision": "fp32", "enable_mkldnn": False, "cpu_threads": 2,
    "text_det_limit_side_len": 1024, "text_det_limit_type": "max", "text_det_thresh": .3,
    "text_det_box_thresh": .6, "text_det_unclip_ratio": 1.5, "text_rec_score_thresh": 0.0}


def verified_models(directory):
    root = Path(directory).resolve(); manifest = read_json(root / "model_manifest.json")
    if manifest["status"] != "complete" or set(manifest["models"]) != set(MODEL_NAMES):
        raise ValueError("Complete exact detector/English recognizer bundle required")
    paths = {}
    for name, model in manifest["models"].items():
        model_dir = (root / model["directory"]).resolve()
        if root not in model_dir.parents:
            raise ValueError("Model directory escapes its bundle")
        actual = {p.relative_to(model_dir).as_posix(): file_identity(p) for p in sorted(model_dir.rglob("*")) if p.is_file()}
        if actual != model["files"] or not actual:
            raise ValueError("Local model files changed or incomplete")
        paths[name] = str(model_dir)
    return paths, file_identity(root / "model_manifest.json")


def normalize_ocr_result(payload):
    result = payload.get("res", payload)
    texts, scores, boxes = (result[key] for key in ("rec_texts", "rec_scores", "rec_polys"))
    if not (len(texts) == len(scores) == len(boxes)) or any(not isinstance(t, str) for t in texts):
        raise ValueError("OCR line text/confidence/box arrays disagree")
    lines = []
    for order, (text, confidence, polygon) in enumerate(zip(texts, scores, boxes)):
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid OCR confidence")
        if (not isinstance(polygon, list) or len(polygon) != 4
                or any(not isinstance(point, list) or len(point) != 2
                       or any(type(v) not in (int, float) or not math.isfinite(v) for v in point) for point in polygon)):
            raise ValueError("Invalid OCR quadrilateral")
        lines.append({"order": order, "text": text, "confidence": confidence, "polygon": polygon})
    raw = "\n".join(texts)  # Preserve engine line order; no table reconstruction or QA corrections.
    return {"raw_text": raw, "search_text": normalize_search_text(raw), "lines": lines,
            "status": "ok" if raw.strip() else "blank_ocr_text"}


def run_ocr_smoke(render_dir, models_dir, output_dir, *, doc_id, page_index, repository_root=".",
                  timeout_seconds=600, progress=None):
    if type(page_index) is not int or page_index < 0 or timeout_seconds <= 0:
        raise ValueError("Zero-based page ID and positive smoke deadline required")
    render, models, output, root = (Path(p).resolve() for p in (render_dir, models_dir, output_dir, repository_root))
    if output.exists(): raise FileExistsError("Use a new immutable OCR smoke directory")
    if render in output.parents or models in output.parents or ((root / ".git").exists() and (root == output or root in output.parents)):
        raise ValueError("OCR outputs must be outside Git and input caches")
    render_manifest = read_json(render / "run_manifest.json")
    if render_manifest["status"] not in {"complete", "sample_complete", "partial"}:
        raise ValueError("Render cache is not finalized for inspection")
    pages_path = render / "render_pages.jsonl"
    if file_identity(pages_path) != render_manifest["render_pages_identity"]:
        raise ValueError("Render page manifest checksum mismatch")
    pages = read_jsonl(pages_path)
    expected = {(d["doc_id"], p) for d in render_manifest["contract"]["documents"] for p in range(d["page_count"])}
    if len(pages) != len(expected) or {(r["doc_id"], r["page_index"]) for r in pages} != expected:
        raise ValueError("Render cohort/page accounting mismatch")
    selected = [r for r in pages if (r["doc_id"], r["page_index"]) == (doc_id, page_index)]
    if len(selected) != 1 or selected[0]["status"] != "ok" or selected[0]["page_index_base"] != 0:
        raise ValueError("Selected physical page is not successfully rendered")
    row = selected[0]; image = (render / row["image_path"]).resolve()
    if render not in image.parents or file_identity(image) != row["image_identity"] or png_info(image) != row["image_info"]:
        raise ValueError("Selected image identity/geometry mismatch")
    model_paths, model_identity = verified_models(models)
    inputs = {"render_manifest": file_identity(render / "run_manifest.json"), "render_pages": file_identity(pages_path),
              "model_manifest": model_identity, "image": row["image_identity"]}
    source = {key: row[key] for key in ("doc_id", "page_index", "page_index_base", "document_sha256", "dpi", "image_info")}
    output.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex, "status": "running", "stage": "ocr_setup_smoke", "code": code_provenance(root),
        "started_utc": datetime.now(timezone.utc).isoformat(), "source": source, "inputs": inputs,
        "configuration": OCR_CONFIG, "package_pins": PACKAGE_PINS, "full_ocr_coverage": False,
        "cohort_totals": render_manifest["cohort_totals"], "selected_pages": 1, "timeout_seconds": timeout_seconds,
        "interpretation": "one-page setup test; no OCR accuracy, retrieval recall, full-report throughput or energy claim"}
    write_json(output / "run_manifest.json", manifest)
    request = {"image": str(image), "source": source, "model_paths": model_paths, "output": str(output)}
    write_json(output / "worker_request.json", request)
    started = time.perf_counter()
    process = None
    try:
        command = [sys.executable, "-m", "finocr.pipelines.ocr_smoke", str(output / "worker_request.json")]
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            last_message = -30.0
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                if elapsed >= timeout_seconds:
                    process.kill(); process.wait()
                    raise TimeoutError("OCR initialization/inference exceeded the smoke deadline; see worker.log")
                if progress and elapsed - last_message >= 30:
                    progress(f"OCR smoke is running ({elapsed:.0f}s); worker.log records initialization/inference")
                    last_message = elapsed
                time.sleep(.1)
        if process.returncode != 0:
            raise RuntimeError("OCR worker failed; see worker.log")
        result = read_json(output / "worker_result.json")
        normalized = normalize_ocr_result(read_json(output / "raw_ocr_result.json"))
        if result["normalized"] != normalized:
            raise ValueError("Worker normalization differs from raw OCR output")
        record = {"schema_version": 1, "run_id": manifest["run_id"], **source, **normalized,
                  "engine": "standard_paddleocr", "engine_version": PACKAGE_PINS["paddleocr"], "device": "cpu",
                  "representation": "ocr_pdf_page_text", "raw_character_count": len(normalized["raw_text"]),
                  "image_sha256": inputs["image"]["sha256"], "error": None}
        write_jsonl(output / "ocr_pages.jsonl", [record])
        manifest.update(status="smoke_complete" if record["status"] == "ok" else "blank_requires_review",
                        timings=result["timings"], runtime=result["runtime"])
        if (file_identity(image) != inputs["image"] or file_identity(pages_path) != inputs["render_pages"]
                or file_identity(render / "run_manifest.json") != inputs["render_manifest"]
                or verified_models(models)[1] != model_identity):
            raise ValueError("OCR input changed during smoke")
    except BaseException as exc:
        if process is not None and process.poll() is None:
            process.kill(); process.wait()
        manifest.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "timed_out" if isinstance(exc, TimeoutError) else "failed",
                        error=f"{type(exc).__name__}: {exc}")
        write_jsonl(output / "ocr_pages.jsonl", [{"schema_version": 1, "run_id": manifest["run_id"], **source,
            "engine": "standard_paddleocr", "engine_version": PACKAGE_PINS["paddleocr"], "device": "cpu",
            "representation": "ocr_pdf_page_text", "image_sha256": inputs["image"]["sha256"],
            "status": manifest["status"], "raw_text": "", "raw_character_count": 0, "search_text": "",
            "lines": [], "error": manifest["error"]}])
        raise
    finally:
        manifest.update(elapsed_seconds=time.perf_counter() - started, finished_utc=datetime.now(timezone.utc).isoformat())
        manifest["artifacts"] = {p.name: file_identity(p) for p in output.iterdir() if p.is_file() and p.name != "run_manifest.json"}
        write_json(output / "run_manifest.json", manifest)
    return {"status": manifest["status"], "output_dir": str(output), "doc_id": doc_id, "page_index": page_index,
            "selected_pages": 1, "full_ocr_coverage": False}


def _worker(request_path):
    request = read_json(request_path); output = Path(request["output"])
    if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
        raise RuntimeError("Use the separate 64-bit Python 3.12 OCR environment")
    actual = {name: importlib.metadata.version(name) for name in PACKAGE_PINS}
    if actual != PACKAGE_PINS:
        raise RuntimeError(f"OCR package pins differ: {actual}")
    print("Importing and initializing the local CPU OCR models", flush=True)
    start = time.perf_counter()
    import paddle
    from paddleocr import PaddleOCR
    paddle.seed(0)
    engine = PaddleOCR(**OCR_CONFIG,
        text_detection_model_name=MODEL_NAMES[0], text_detection_model_dir=request["model_paths"][MODEL_NAMES[0]],
        text_recognition_model_name=MODEL_NAMES[1], text_recognition_model_dir=request["model_paths"][MODEL_NAMES[1]])
    initialized = time.perf_counter()
    print("Processing the selected source PNG", flush=True)
    results = list(engine.predict(request["image"]))
    if len(results) != 1: raise ValueError("Exactly one image result required")
    payload = results[0].json
    write_json(output / "raw_ocr_result.json", payload)
    normalized = normalize_ocr_result(payload)
    write_json(output / "worker_result.json", {"normalized": normalized,
        "timings": {"imports_and_initialization_seconds": initialized-start, "inference_and_serialization_seconds": time.perf_counter()-initialized},
        "runtime": {"packages": actual, "python": sys.version, "paddle_device": paddle.device.get_device(),
                    "compiled_with_cuda": paddle.is_compiled_with_cuda()}})


if __name__ == "__main__":
    _worker(sys.argv[1])
