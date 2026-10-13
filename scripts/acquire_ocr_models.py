"""Explicit standard PaddleOCR model acquisition, separate from inference."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import urlretrieve


MODELS = ("PP-OCRv5_mobile_det", "en_PP-OCRv5_mobile_rec")


def identity(path):
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size}


def acquire(destination):
    root = Path(destination).resolve()
    if root.exists():
        raise FileExistsError("Model bundle already exists; retain it and verify the saved manifest rather than redownloading")
    root.mkdir(parents=True)
    manifest = {"schema_version": 1, "status": "acquiring", "stage": "setup_model_acquisition", "models": {},
                "hash_policy": "Initial hashes are observed acquisition identities, not publisher-provided expected hashes; retain these exact bytes for reproduction"}
    try:
        for name in MODELS:
            url = f"https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/{name}_infer.tar"
            archive = root / f"{name}_infer.tar"
            print(f"Downloading pinned model name: {name}", flush=True)
            urlretrieve(url, archive)
            target = root / name; target.mkdir()
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    relative = Path(member.name)
                    if relative.is_absolute() or ".." in relative.parts or member.issym() or member.islnk():
                        raise ValueError("Unsafe model archive entry")
                bundle.extractall(target, filter="data")
            candidates = list(target.rglob("inference.yml"))
            if len(candidates) != 1:
                raise ValueError("Expected one model inference.yml")
            model_dir = candidates[0].parent
            manifest["models"][name] = {"url": url, "archive": identity(archive),
                "directory": str(model_dir.relative_to(root)),
                "files": {str(p.relative_to(model_dir)).replace("\\", "/"): identity(p)
                          for p in sorted(model_dir.rglob("*")) if p.is_file()}}
        manifest["status"] = "complete"
    except BaseException as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (root / "model_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    acquire(parser.parse_args().output_dir)
