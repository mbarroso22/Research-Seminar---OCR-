"""Export the supplied CPU diagnostic's exact non-framework pins using stdlib only."""
import argparse
import hashlib
import json
from pathlib import Path


def prepare(cpu_dir, output):
    root, destination = Path(cpu_dir).resolve(), Path(output)
    data = (root / "run_manifest.json").read_bytes()
    if hashlib.sha256(data).hexdigest() != "cd0fa0c899c9298dcc75194318114b6b947840fd663a4847ced4cf6452412d7e":
        raise ValueError("Use the retained eight-page CPU diagnostic snapshot, not the continuing CPU run")
    manifest = json.loads(data)
    for name, identity in manifest["artifacts"].items():
        path = (root / name).resolve()
        if root not in path.parents or not path.is_file(): raise ValueError(f"Missing/unsafe CPU reference artifact: {name}")
        if path.stat().st_size != identity["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != identity["sha256"]:
            raise ValueError(f"CPU reference artifact changed: {name}")
    packages = manifest["contract"]["runtime"]["packages"]
    if packages.get("paddlepaddle") != "3.3.0" or "paddlepaddle-gpu" in packages:
        raise ValueError("Unexpected CPU framework reference")
    if destination.exists(): raise FileExistsError("Keep the previous requirements snapshot; use a new output file")
    pins = [f"{name}=={version}" for name, version in sorted(packages.items())
            if name not in {"paddlepaddle", "financial-ocr-research"}]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("# Exact non-framework pins from CPU diagnostic ad4cddfa7ac7489b8839275df9baf870\n" + "\n".join(pins) + "\n", encoding="utf-8")
    return len(pins)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-dir", required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(f"Saved {prepare(args.cpu_dir, args.output)} exact non-framework package pins; GPU Paddle is installed separately")
