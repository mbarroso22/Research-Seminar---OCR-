"""Locate the preserved original GPU OCR cache; optionally materialize its ZIP.

Standard library only. No package installation, OCR, encoder, or task parsing.
The comparison CLI subsequently verifies every committed OCR record/raw artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

OCR_MANIFEST_SHA256 = "c79e71c736ca6fe1f33d3fc7cdae039f212d01a094a209c3cd9eb17324afcf0d"


def sha(data): return hashlib.sha256(data).hexdigest()


def locate_cache(imports, destination):
    imports, destination = Path(imports).resolve(), Path(destination).resolve()
    if not imports.is_dir(): raise ValueError(f"Missing preserved imports directory: {imports}")
    if destination == imports or imports in destination.parents or destination in imports.parents:
        raise ValueError("Materialized cache must be outside preserved imports")
    for manifest in sorted(imports.rglob("run_manifest.json")):
        if sha(manifest.read_bytes()) == OCR_MANIFEST_SHA256:
            return {"ocr_dir": str(manifest.parent), "source": str(manifest), "materialized": False}
    for archive in sorted(imports.rglob("*.zip")):
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                normalized = name.replace("\\", "/")
                if normalized.split("/")[-1] != "run_manifest.json": continue
                if sha(z.read(name)) != OCR_MANIFEST_SHA256: continue
                prefix = normalized[:-len("run_manifest.json")]
                if destination.exists(): raise FileExistsError("Preserve existing materialized directory; choose a new destination")
                members, seen = [], set()
                for info in z.infolist():
                    candidate = info.filename.replace("\\", "/")
                    if not candidate.startswith(prefix) or info.is_dir(): continue
                    relative = candidate[len(prefix):]; pure = PurePosixPath(relative)
                    if (not relative or pure.is_absolute() or any(p in ("..", ".") or ":" in p for p in pure.parts)
                            or relative.casefold() in seen):
                        raise ValueError("Unsafe/duplicate archive member in original OCR cache")
                    seen.add(relative.casefold()); members.append((info, pure))
                destination.mkdir(parents=True)
                for info, relative in members:
                    target = destination.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as out, z.open(info) as source:
                        while block := source.read(1024 * 1024): out.write(block)
                if sha((destination / "run_manifest.json").read_bytes()) != OCR_MANIFEST_SHA256:
                    raise ValueError("Materialized manifest checksum differs")
                return {"ocr_dir": str(destination), "source": str(archive), "materialized": True}
    raise ValueError("Original completed GPU cache not found by exact manifest identity; do not substitute the broader cohort")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imports", required=True); parser.add_argument("--destination", required=True)
    parser.add_argument("--output", required=True); args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists(): raise FileExistsError("Preserve existing input location evidence")
    result = locate_cache(args.imports, args.destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as f: json.dump(result, f, indent=2); f.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
