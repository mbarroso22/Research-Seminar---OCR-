"""Inference is paused. Use check_answer_contract.py for offline checks only."""
import argparse
import json
from pathlib import Path
from finocr_answer.feasibility import run
from finocr_answer.pause import InferencePausedError


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--setup',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:result=run(a.setup,a.output,Path(__file__).resolve().parents[1])
    except InferencePausedError as exc:
        print(json.dumps({'status':'inference_paused','inference_executed':0,'additional_inference_authorized':0,'error':str(exc)},indent=2))
        return 2
    print(json.dumps(result,indent=2))
    return 0 if result['automated_checks_pass'] else 1


if __name__=='__main__': raise SystemExit(main())
