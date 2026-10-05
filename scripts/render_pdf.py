from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a PDF once for matched OCR inputs")
    parser.add_argument("pdf")
    parser.add_argument("output_dir")
    parser.add_argument("--dpi", type=int, default=200)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit("Install PDF support first: python -m pip install -e '.[pdf]'") from exc

    pdf_path = Path(args.pdf)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = args.dpi / 72
    manifest: list[dict[str, object]] = []
    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            target = output_dir / f"page_{page_index:04d}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest.append(
                {"page_index": page_index, "path": str(target), "sha256": digest, "dpi": args.dpi}
            )
    (output_dir / "render_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Rendered {len(manifest)} pages to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

