"""Immutable acquisition and local conversion, outside all baseline environments."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
import platform
import struct
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from .contract import canonical, digest, VERSION, SCHEMA, INSTRUCTION
from finocr.io import write_json
from .pause import require_inference_authorized


def sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): result.update(block)
    return result.hexdigest()


def identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "size": path.stat().st_size, "sha256": sha(path)}


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)).replace("\\", "/"): identity(p)["sha256"]
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def source_identity(repository: Path) -> str:
    files = [*sorted((repository / "src/finocr_answer").glob("*.py")),
             *sorted((repository / "scripts").glob("*answer*.py")),
             repository / "docs/ANSWER_SETUP_LOCK.json", repository / "requirements/answer-windows-py312.lock.txt"]
    return digest({str(p.relative_to(repository)): sha(p) for p in files})


def download(url: str, destination: Path, expected: str) -> None:
    if destination.exists():
        if sha(destination) != expected: raise ValueError(f"Existing file differs; preserved: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists(): raise ValueError(f"Interrupted download preserved: {temporary}; remove only that partial to retry acquisition")
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("xb") as out:
        while block := response.read(1024 * 1024): out.write(block)
    if sha(temporary) != expected: raise ValueError(f"Download checksum mismatch: {temporary}")
    temporary.replace(destination)


def acquire(lock: dict, root: Path) -> dict:
    if any(p in {".venv", ".venv-ocr", ".venv-ocr-gpu"} for p in root.resolve().parts):
        raise ValueError("Answer assets cannot be placed inside existing environments")
    root.mkdir(parents=True, exist_ok=True)
    for file in lock["model_files"]:
        name = file["name"]
        download(f"https://huggingface.co/{lock['model_id']}/resolve/{lock['model_revision']}/{name}", root / "official" / name, file["sha256"])
    archive = root / "downloads/backend.zip"
    download(lock["backend_url"], archive, lock["backend_zip_sha256"])
    backend = root / "backend"
    # Do not use extractall: validate paths and compare every existing byte.
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            relative = Path(item.filename.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
                raise ValueError("Unsafe archive path")
            if item.is_dir(): continue
            target = backend / relative
            data = bundle.read(item)
            if target.exists() and target.read_bytes() != data:
                raise ValueError(f"Existing backend differs; preserved: {target}")
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as handle: handle.write(data)
    result = {"lock_sha256": digest(lock), "official_files": tree(root / "official"),
              "backend_files": tree(backend), "archive": identity(archive)}
    target = root / "acquisition.json"
    if target.exists() and json.loads(target.read_text()) != result: raise ValueError("Acquisition identity changed")
    write_json(target, result)
    return {"status": "assets_verified", "generation_executed": False}


def executable(root: Path, name: str) -> Path:
    candidates = list((root / "backend").rglob(name))
    if len(candidates) != 1: raise ValueError(f"Expected one {name}")
    return candidates[0]


def runtime() -> dict:
    return {"python": platform.python_version(), "bits": struct.calcsize("P")*8,
            "platform": platform.platform(), "executable": str(Path(sys.executable).resolve()),
            "packages": dict(sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions()))}


def verify_assets(lock: dict, root: Path) -> dict:
    acquisition = json.loads((root / "acquisition.json").read_text())
    if acquisition["lock_sha256"] != digest(lock): raise ValueError("Setup lock changed")
    if tree(root / "official") != acquisition["official_files"] or tree(root / "backend") != acquisition["backend_files"]:
        raise ValueError("Source model or backend changed")
    if sha(root / "downloads/backend.zip") != lock["backend_zip_sha256"]: raise ValueError("Backend archive changed")
    return acquisition


def convert(lock: dict, root: Path, llama_source: Path) -> dict:
    verify_assets(lock, root)
    if platform.python_version() != lock['python'] or struct.calcsize('P')*8 != 64:
        raise ValueError("Use isolated CPython 3.12.10 x64")
    commit = subprocess.check_output(['git', '-C', str(llama_source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(llama_source), 'status', '--porcelain', '--untracked-files=all'], text=True)
    if commit != lock['backend_commit'] or dirty.strip(): raise ValueError("Converter checkout is not the clean pinned commit")
    output = root / "converted"
    if output.exists(): raise ValueError("Conversion directory already exists; preserve it and inspect logs before any new conversion")
    output.mkdir()
    environment = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUDA_VISIBLE_DEVICES='')
    commands = [[sys.executable, str(llama_source/'convert_hf_to_gguf.py'), str(root/'official'), '--outfile', str(output/'model-f16.gguf'), '--outtype', 'f16'],
                [str(executable(root, 'llama-quantize.exe')), str(output/'model-f16.gguf'), str(output/'model-Q4_K_M.gguf'), 'Q4_K_M', '6']]
    record = {"status": "running", "commands": commands, "converter_commit": commit, "runtime": runtime()}
    write_json(output/'conversion.json', record)
    for index, command in enumerate(commands):
        with (output/f'{index+1}.log').open('wb') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
        if result.returncode:
            record.update(status='failed', exit_code=result.returncode); write_json(output/'conversion.json', record)
            raise ValueError('Conversion failed; logs and partial files preserved')
    record.update(status='complete', model=identity(output/'model-Q4_K_M.gguf'), intermediate=identity(output/'model-f16.gguf'))
    write_json(output/'conversion.json', record)
    return {"status": "converted", "model": record['model'], "generation_executed": False}


def seal(lock: dict, root: Path, repository: Path) -> dict:
    require_inference_authorized()  # revised contract is offline only, not an inference seal
    target=root/'setup_manifest.json'
    if target.exists() and json.loads(target.read_text()).get('version')=='bounded-answer-preparation-v1':
        raise ValueError('Preserve the original v1 setup and ledger; use prepare_answer_followup.py for the separately budgeted v2 condition')
    verify_assets(lock, root)
    conversion = json.loads((root/'converted/conversion.json').read_text())
    if conversion['status'] != 'complete' or conversion['runtime'] != runtime(): raise ValueError('Conversion incomplete or isolated runtime changed')
    model = root/'converted/model-Q4_K_M.gguf'
    if identity(model) != conversion['model']: raise ValueError('Converted model changed')
    server = executable(root, 'llama-server.exe')
    version = subprocess.check_output([str(server), '--version'], stderr=subprocess.STDOUT, text=True)
    if '6500' not in version or 'a7a98e0' not in version: raise ValueError('Unexpected backend build')
    result = {"version": VERSION, "lock": lock, "asset_root": str(root.resolve()), "model": identity(model),
              "server": identity(server), "backend_files": tree(root/'backend'), "official_files": tree(root/'official'),
              "runtime": runtime(), "conversion_sha256": sha(root/'converted/conversion.json'),
              "backend_version": version, "source_sha256": source_identity(repository),
              "instruction_sha256": hashlib.sha256(INSTRUCTION.encode()).hexdigest(), "schema_sha256": digest(SCHEMA),
              "benchmark_generation_enabled": False}
    target = root/'setup_manifest.json'
    if target.exists() and json.loads(target.read_text()) != result: raise ValueError('Existing setup seal differs; preserved')
    write_json(target, result)
    return {"status": "setup_sealed_not_feasibility_validated", "manifest": str(target), "generation_executed": False}
