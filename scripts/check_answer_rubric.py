"""Evaluator-only read-only source audit. No model/backend imports or calls."""
import argparse
import json
from pathlib import Path
from finocr_answer.evaluator import check_private_key
from finocr.io import write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key', type=Path, required=True)
    p.add_argument('--pdf-root', type=Path, required=True)
    p.add_argument('--tasks', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--require-freeze-ready', action='store_true')
    a = p.parse_args()
    if a.output.exists(): raise ValueError('Output exists; preserve the prior audit')
    result = check_private_key(a.key, a.pdf_root, a.tasks, freeze=a.require_freeze_ready)
    write_json(a.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
