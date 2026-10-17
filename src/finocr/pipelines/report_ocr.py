"""Resumable report OCR: immutable attempts, one worker per report and device."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import time
import uuid

from finocr.io import read_json, write_json, write_jsonl
from finocr.pipelines.native_baseline import code_provenance
from finocr.pipelines.ocr_data import (COMPLETED, FAILURES, SOURCE_FIELDS, coverage, full_render,
                                      inside, require, validate_text_record, verify_image)
from finocr.pipelines.ocr_smoke import OCR_CONFIG, PACKAGE_PINS, create_ocr_engine, normalize_ocr_result, verified_models
from finocr.pipelines.ocr_device import device_condition, synchronize, validate_worker_runtime
from finocr.pipelines.report_rendering import file_identity, safe_document_name


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def runtime_identity(device="cpu"):
    require(sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8,
            "Use the existing separate 64-bit Python 3.12 OCR environment")
    packages = {d.metadata["Name"].lower().replace("_", "-"): d.version for d in importlib.metadata.distributions()}
    _, pins = device_condition(device)
    require(all(importlib.metadata.version(k) == v for k, v in pins.items()), "OCR package pins changed")
    opposite = "paddlepaddle-gpu" if device == "cpu" else "paddlepaddle"
    require(opposite not in packages, "CPU and GPU Paddle distributions require separate environments")
    return {"python": sys.version, "bits": 64, "packages": dict(sorted(packages.items()))}


@contextmanager
def cache_lock(output):
    # OS locks release after a crash; keep the file to avoid unlink/reopen races.
    with (output / ".ocr.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell(): handle.write(b"0"); handle.flush()
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another OCR process holds this cache; use one process per output directory") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ReportWorker:
    def __init__(self, model_paths, session_dir, initialization_timeout, progress=None, device="cpu"):
        self.session_dir = session_dir; self.process = None; self.progress = progress
        session_dir.mkdir(parents=True)
        self.log = (session_dir / "worker.log").open("w", encoding="utf-8")
        request = {"model_paths": model_paths, "session_dir": str(session_dir)}
        if device != "cpu": request["device"] = device
        write_json(session_dir / "startup.json", request)
        try:
            self.process = subprocess.Popen([sys.executable, "-m", "finocr.pipelines.report_ocr",
                str(session_dir / "startup.json")], stdin=subprocess.PIPE, stdout=self.log,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8")
            self.ready = self.wait(session_dir / "ready.json", initialization_timeout, "model initialization")
            require(self.ready["status"] == "ready", "OCR worker initialization failed")
            validate_worker_runtime(self.ready["runtime"], device)
        except BaseException:
            self.close(); raise

    def wait(self, path, timeout, stage):
        start = time.perf_counter(); last = -30.0
        while not path.is_file():
            if self.process.poll() is not None:
                raise RuntimeError(f"OCR worker exited during {stage}; see {self.session_dir / 'worker.log'}")
            elapsed = time.perf_counter() - start
            if elapsed >= timeout:
                self.process.kill(); self.process.wait()
                raise TimeoutError(f"OCR {stage} exceeded {timeout:g}s; see {self.session_dir / 'worker.log'}")
            if self.progress and elapsed - last >= 30:
                self.progress(f"OCR {stage} running ({elapsed:.0f}s); worker log: {self.session_dir / 'worker.log'}")
                last = elapsed
            time.sleep(.1)
        return read_json(path)

    def page(self, image, image_identity, attempt_dir, timeout):
        self.process.stdin.write(json.dumps({"image": str(image), "image_identity": image_identity,
                                            "output": str(attempt_dir)}) + "\n")
        self.process.stdin.flush()
        return self.wait(attempt_dir / "worker_result.json", timeout, "page inference")

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('{"stop":true}\n'); self.process.stdin.flush()
                    self.process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    self.process.kill(); self.process.wait()
            if self.process.stdin is not None:
                try: self.process.stdin.close()
                except OSError: pass
        if not self.log.closed: self.log.close()


def _worker(startup_path):
    startup = read_json(startup_path); session = Path(startup["session_dir"])
    device = startup.get("device", "cpu")
    start = time.perf_counter()
    try:
        engine, runtime, initialization = (create_ocr_engine(startup["model_paths"]) if device == "cpu"
                                           else create_ocr_engine(startup["model_paths"], device=device))
        write_json(session / "ready.json", {"status": "ready", "runtime": runtime, "initialization_seconds": initialization})
    except Exception as exc:
        write_json(session / "ready.json", {"status": "failed", "error": f"{type(exc).__name__}: {exc}",
                                           "initialization_seconds": time.perf_counter()-start})
        raise
    for line in sys.stdin:
        request = json.loads(line)
        if request.get("stop") is True: break
        output = Path(request["output"]); image = Path(request["image"]); started = time.perf_counter()
        try:
            require(file_identity(image) == request["image_identity"], "Image changed before inference")
            synchronize(device)
            results = list(engine.predict(str(image)))
            synchronize(device)
            payload = results[0].json if len(results) == 1 else {"unexpected_results": [r.json for r in results]}
            write_json(output / "raw_ocr_result.json", payload)
            require(len(results) == 1, "Exactly one image result required")
            normalized = normalize_ocr_result(payload)
            require(file_identity(image) == request["image_identity"], "Image changed during inference")
            result = {"status": normalized["status"], "normalized": normalized, "error": None}
        except Exception as exc:
            result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            print(result["error"], flush=True)
        result["inference_and_serialization_seconds"] = time.perf_counter()-started
        write_json(output / "worker_result.json", result)


def pending(plan, run_id, device="cpu"):
    return {"schema_version": 1, "run_id": run_id, **plan, "status": "pending", "raw_text": "", "search_text": "",
        "lines": [], "raw_character_count": 0, "error": None, "engine": "standard_paddleocr",
        "engine_version": PACKAGE_PINS["paddleocr"], "device": device, "representation": "ocr_pdf_page_text",
        "attempt_count": 0, "attempt_history": [], "ocr_attempted": False}


def commit_attempt(output, attempt_dir, row):
    artifacts = {p.name: file_identity(p) for p in attempt_dir.iterdir() if p.is_file() and p.name != "record.json"}
    row = {**row, "attempt_artifacts": artifacts}
    record = attempt_dir / "record.json"
    write_json(record, {"record": row, "record_sha256": digest(row)})
    return {**row, "record_path": record.relative_to(output).as_posix(), "record_identity": file_identity(record)}


def validate_commit(output, record_path, plan, contract, run_id):
    envelope = read_json(record_path); row = envelope["record"]
    require(digest(row) == envelope["record_sha256"], "OCR committed record checksum mismatch")
    require(all(row[k] == plan[k] for k in (*SOURCE_FIELDS, "image_path")) and row["run_id"] == run_id,
            "OCR committed source mapping changed")
    require(row["configuration_sha256"] == digest(contract["configuration"])
            and row["model_manifest_identity"] == contract["model_manifest"]
            and row["runtime_identity"] == contract["runtime"] and row["device"] == contract["configuration"]["device"]
            and row["engine_version"] == PACKAGE_PINS["paddleocr"], "OCR committed condition/runtime mismatch")
    validate_text_record(row)
    require(row["status"] != "pending" and type(row["attempt_count"]) is int and row["attempt_count"] > 0,
            "Committed OCR attempts cannot be pending")
    for name, identity in row["attempt_artifacts"].items():
        require(Path(name).name == name and file_identity(record_path.parent / name) == identity,
                "OCR raw/attempt artifact checksum mismatch")
    if row["status"] in COMPLETED:
        normalized = normalize_ocr_result(read_json(record_path.parent / "raw_ocr_result.json"))
        require(all(row[k] == normalized[k] for k in ("status", "raw_text", "search_text", "lines")),
                "OCR committed text differs from raw model output")
        worker = read_json(record_path.parent / "worker_result.json")
        require(worker["normalized"] == normalized and worker["status"] == normalized["status"], "OCR worker/raw output mismatch")
    return {**row, "record_path": record_path.relative_to(output).as_posix(), "record_identity": file_identity(record_path)}


def attempt_base(plan, manifest, directory, history, session):
    return {**pending(plan, manifest["run_id"], manifest["contract"]["configuration"]["device"]), "attempt_count": len(history)+1,
        "attempt_history": [*history, directory.relative_to(Path(manifest["output_dir"])).as_posix()],
        "configuration_sha256": digest(manifest["contract"]["configuration"]),
        "model_manifest_identity": manifest["contract"]["model_manifest"], "runtime_identity": manifest["contract"]["runtime"],
        "worker_session": session, "elapsed_seconds": None, "inference_and_serialization_seconds": None}


def recover_records(output, plans, manifest):
    rows = []
    known = {r["record_path"]: r["record_identity"] for r in
             (read_jsonl_if_valid(output / "ocr_pages.jsonl", manifest)) if "record_path" in r}
    for plan in plans:
        parent = output / "attempts" / safe_document_name(plan["doc_id"]) / f"page_{plan['page_index']:05d}"
        row = pending(plan, manifest["run_id"], manifest["contract"]["configuration"]["device"]); history = []
        if parent.exists():
            dirs = sorted(p for p in parent.iterdir() if p.is_dir())
            require([p.name for p in dirs] == [f"attempt_{i:04d}" for i in range(1, len(dirs)+1)], "OCR attempt sequence changed")
            for directory in dirs:
                record = directory / "record.json"
                if record.is_file():
                    if record.relative_to(output).as_posix() in known:
                        require(file_identity(record) == known[record.relative_to(output).as_posix()], "Retained OCR record bytes changed")
                    row = validate_commit(output, record, plan, manifest["contract"], manifest["run_id"])
                    require(row["attempt_history"] == [*history, directory.relative_to(output).as_posix()], "OCR attempt history changed")
                else:
                    interrupted = attempt_base(plan, manifest, directory, history, None)
                    interrupted.update(status="interrupted", error="Prior attempt was not committed; retained raw files, retry required")
                    row = commit_attempt(output, directory, interrupted)
                history = row["attempt_history"]
        rows.append(row)
    return rows


def read_jsonl_if_valid(path, manifest):
    from finocr.io import read_jsonl
    # Aggregate files are rebuildable indexes over immutable attempt commits.
    if path.is_file() and file_identity(path) == manifest.get("artifacts", {}).get(path.name):
        return read_jsonl(path)
    return []


def timing_summary(output, rows, executions):
    attempts, inference, wall, startup_wall, unknown = 0, 0.0, 0.0, 0.0, 0
    for row in rows:
        for relative in row["attempt_history"]:
            old = read_json(inside(output, relative + "/record.json"))["record"]
            attempts += 1
            if old["elapsed_seconds"] is None: unknown += 1
            else: wall += old["elapsed_seconds"]
            startup_wall += old.get("initialization_wall_seconds", 0.0)
            inference += old["inference_and_serialization_seconds"] or 0.0
    ready_files = list((output / "sessions").glob("*/ready.json")) if (output / "sessions").exists() else []
    return {"page_attempts": attempts, "page_attempt_wall_seconds": max(0.0, wall-startup_wall),
        "worker_initialization_wall_seconds": startup_wall, "page_attempts_with_unknown_duration": unknown,
        "worker_page_seconds": inference, "model_initialization_seconds": sum(read_json(p)["initialization_seconds"] for p in ready_files),
        "worker_initializations": sum(read_json(p)["status"] == "ready" for p in ready_files),
        "worker_startup_attempts": len(list((output / "sessions").glob("*"))) if (output / "sessions").exists() else 0,
        "failed_initializations": sum(read_json(p)["status"] == "failed" for p in ready_files),
        "recorded_invocation_wall_seconds": sum(e.get("elapsed_seconds") or 0 for e in executions),
        "unfinished_invocations": sum(e.get("finished_utc") is None for e in executions),
        "policy": "cumulative actual invocations/attempts including retries and diagnostic reuse; fixed-order descriptive timing, not energy or a repeated latency benchmark"}


def snapshot(output, manifest, rows, status):
    write_jsonl(output / "ocr_pages.jsonl", rows)
    manifest.update(status=status, coverage=coverage(rows), full_ocr_coverage=all(r["status"] in COMPLETED for r in rows),
                    timing=timing_summary(output, rows, manifest["executions"]), page_record_count=len(rows))
    manifest["artifacts"] = {"ocr_pages.jsonl": file_identity(output / "ocr_pages.jsonl"),
        **{p.relative_to(output).as_posix(): file_identity(p) for p in (output / "source-render").glob("*") if p.is_file()},
        **{p.relative_to(output).as_posix(): file_identity(p) for p in (output / "sessions").glob("*/*") if p.is_file()}}
    write_json(output / "run_manifest.json", manifest)


def run_report_ocr(render_dir, models_dir, output_dir, *, repository_root=".", resume=False, selection_path=None,
                   page_timeout=600, initialization_timeout=180, max_pages=None, progress=None, device="cpu"):
    started = time.perf_counter(); started_utc = utc()
    configuration, pins = device_condition(device)
    require(math.isfinite(page_timeout) and math.isfinite(initialization_timeout) and page_timeout > 0 and initialization_timeout > 0
            and (max_pages is None or type(max_pages) is int and max_pages > 0),
            "Positive OCR deadlines/page limit required")
    render, models, output, root = (Path(p).resolve() for p in (render_dir, models_dir, output_dir, repository_root))
    require(not (root / ".git").exists() or not (output == root or root in output.parents), "OCR cache must be outside Git")
    require(all(output != p and p not in output.parents and output not in p.parents for p in (render, models)),
            "OCR cache must be separate from rendering/model inputs")
    if output.exists() and not resume: raise FileExistsError("OCR cache exists; use explicit --resume")
    if resume: require((output / "run_manifest.json").is_file(), "Resume requires an OCR run manifest")
    render_manifest, plans, inputs = full_render(render, verify_images=True)
    model_paths, model_identity = verified_models(models)
    runtime = runtime_identity() if device == "cpu" else runtime_identity(device)
    code = code_provenance(root)
    contract = {**inputs, "render_contract": render_manifest["contract"], "model_manifest": model_identity,
        "configuration": configuration, "package_pins": pins, "runtime": runtime,
        "python_source_sha256": code["python_source_sha256"], "page_timeout_seconds": page_timeout,
        "initialization_timeout_seconds": initialization_timeout}
    if device == "gpu:0":
        contract["gpu_runtime_condition"] = {"wheel_channel": "https://www.paddlepaddle.org.cn/packages/stable/cu118/",
            "cuda": "11.8", "page_timing": "paddle.device.synchronize before and after predict; includes serialization"}
    keys = {(r["doc_id"], r["page_index"]) for r in plans}
    mode, selection_identity = "full", None
    if selection_path is not None:
        selection = read_json(selection_path); selection_identity = file_identity(selection_path)
        require(selection["policy"]["version"] == "source-financial-tables-v1" and selection["inputs"]["render_manifest"] == inputs["render_manifest"]
                and selection["inputs"]["render_pages"] == inputs["render_pages"], "Diagnostic selection/render identity mismatch")
        chosen = [(r["doc_id"], r["page_index"]) for r in selection["pages"]]
        require(chosen and len(chosen) == len(set(chosen)) and set(chosen) <= keys
                and all(type(p) is int for _, p in chosen), "Invalid diagnostic source page selection")
        keys = set(chosen); mode = "diagnostic"
    if progress: progress(f"Verified {len(plans)} source images and fixed {device} model/runtime identities")
    output.mkdir(parents=True, exist_ok=True)
    with cache_lock(output):
        if (output / "run_manifest.json").exists():
            require(resume, "OCR manifest already exists; use --resume")
            manifest = read_json(output / "run_manifest.json")
            require(manifest["contract"] == contract, "OCR resume inputs/configuration/runtime/source changed; create a new condition/cache")
            for name, identity in manifest.get("artifacts", {}).items():
                if name != "ocr_pages.jsonl":
                    require(file_identity(inside(output, name)) == identity, "Retained OCR worker artifact changed")
        else:
            manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex, "stage": "full_report_ocr", "output_dir": str(output),
                "started_utc": started_utc, "contract": contract, "code": code,
                "cohort_totals": render_manifest["cohort_totals"], "executions": [], "page_index_base": 0}
            snapshot_dir = output / "source-render"; snapshot_dir.mkdir()
            for name in ("run_manifest.json", "render_pages.jsonl"):
                temporary = snapshot_dir / (name + ".tmp")
                shutil.copyfile(render / name, temporary); temporary.replace(snapshot_dir / name)
        require(full_render(output / "source-render")[2] == inputs, "Retained rendering snapshot changed")
        rows = recover_records(output, plans, manifest)
        execution = {"started_utc": started_utc, "mode": mode, "selection_identity": selection_identity,
                     "selected_pages": len(keys), "max_pages": max_pages, "validation_seconds": time.perf_counter()-started}
        manifest["executions"].append(execution); manifest["mode"] = mode; manifest.pop("error", None)
        snapshot(output, manifest, rows, "running")
        attempted, worker, status = 0, None, "running"
        try:
            for doc in render_manifest["contract"]["documents"]:
                initialization_error = None
                indices = [i for i, r in enumerate(rows) if r["doc_id"] == doc["doc_id"]
                           and (r["doc_id"], r["page_index"]) in keys and r["status"] not in COMPLETED]
                for i in indices:
                    if max_pages is not None and attempted >= max_pages: break
                    plan, old = plans[i], rows[i]
                    directory = output / "attempts" / safe_document_name(plan["doc_id"]) / f"page_{plan['page_index']:05d}" / f"attempt_{old['attempt_count']+1:04d}"
                    directory.mkdir(parents=True, exist_ok=False)
                    attempted += 1
                    row = attempt_base(plan, manifest, directory, old["attempt_history"], None)
                    row["initialization_wall_seconds"] = 0.0
                    write_json(directory / "request.json", {"source": {k: plan[k] for k in SOURCE_FIELDS},
                        "image": str(inside(render, plan["image_path"])), "configuration": configuration, "model_manifest": model_identity})
                    attempt_started = time.perf_counter()
                    try:
                        if progress: progress(f"OCR {plan['doc_id']} zero-based page {plan['page_index']} (attempt {row['attempt_count']})")
                        if initialization_error is not None:
                            raise RuntimeError("Report worker initialization previously failed: " + initialization_error)
                        if worker is None:
                            session = output / "sessions" / uuid.uuid4().hex
                            row["worker_session"] = session.relative_to(output).as_posix()
                            initialization_started = time.perf_counter()
                            try:
                                worker = (ReportWorker(model_paths, session, initialization_timeout, progress) if device == "cpu"
                                          else ReportWorker(model_paths, session, initialization_timeout, progress, device=device))
                            except Exception as exc:
                                initialization_error = f"{type(exc).__name__}: {exc}"
                                raise
                            finally:
                                row["initialization_wall_seconds"] = time.perf_counter()-initialization_started
                        row["worker_session"] = worker.session_dir.relative_to(output).as_posix()
                        image = verify_image(render, plan); row["ocr_attempted"] = True
                        result = worker.page(image, plan["image_identity"], directory, page_timeout)
                        row["inference_and_serialization_seconds"] = result["inference_and_serialization_seconds"]
                        if result["status"] in COMPLETED:
                            normalized = normalize_ocr_result(read_json(directory / "raw_ocr_result.json"))
                            require(normalized == result["normalized"] and normalized["status"] == result["status"], "Worker raw/normalization mismatch")
                            row.update(normalized, raw_character_count=len(normalized["raw_text"]))
                        else:
                            require(result["status"] == "failed", "Unexpected worker page status")
                            row.update(status="failed", error=result["error"])
                        verify_image(render, plan)
                    except BaseException as exc:
                        row.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "timed_out" if isinstance(exc, TimeoutError) else "failed",
                                   error=f"{type(exc).__name__}: {exc}", raw_text="", search_text="", lines=[], raw_character_count=0)
                        if worker is not None: worker.close(); worker = None
                        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                            row["elapsed_seconds"] = time.perf_counter()-attempt_started
                            rows[i] = commit_attempt(output, directory, row)
                            raise
                    row["elapsed_seconds"] = time.perf_counter()-attempt_started
                    rows[i] = commit_attempt(output, directory, row)
                if worker is not None: worker.close(); worker = None
                snapshot(output, manifest, rows, "running")
                if max_pages is not None and attempted >= max_pages: break
            require(full_render(render, verify_images=True)[2] == inputs and verified_models(models)[1] == model_identity,
                    "OCR source/model inputs changed during ingestion")
            chosen_rows = [r for r in rows if (r["doc_id"], r["page_index"]) in keys]
            status = "paused" if any(r["status"] == "pending" for r in chosen_rows) else "partial" if any(r["status"] in FAILURES for r in chosen_rows) else "complete"
            if mode == "diagnostic" and status in {"partial", "complete"}: status = "diagnostic_"+status
        except BaseException as exc:
            status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if worker is not None: worker.close()
            execution.update(finished_utc=utc(), elapsed_seconds=time.perf_counter()-started, newly_attempted_pages=attempted)
            snapshot(output, manifest, rows, status)
        return {"status": status, "output_dir": str(output), "run_id": manifest["run_id"],
                "coverage": manifest["coverage"], "full_ocr_coverage": manifest["full_ocr_coverage"]}


if __name__ == "__main__":
    _worker(sys.argv[1])
