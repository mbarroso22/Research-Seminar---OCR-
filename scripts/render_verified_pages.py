"""Thin wrapper for Phase 0 PDF evidence-page rendering."""

from __future__ import annotations

import sys

from finocr.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["render-pages", *sys.argv[1:]]))

