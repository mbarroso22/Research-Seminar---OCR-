"""Acquire/convert/seal only. Never launches an inference request."""
import argparse
import json
from pathlib import Path
from finocr_answer.setup import acquire, convert, seal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['acquire', 'convert', 'seal'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--llama-source', type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    lock = json.loads((repository/'docs/ANSWER_SETUP_LOCK.json').read_text())
    if args.stage == 'acquire': result = acquire(lock, args.root.resolve())
    elif args.stage == 'convert':
        if not args.llama_source: parser.error('--llama-source required for conversion')
        result = convert(lock, args.root.resolve(), args.llama_source.resolve())
    else: result = seal(lock, args.root.resolve(), repository)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
