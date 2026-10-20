"""Read-only export of offline review or future campaign evidence; no inference."""
import argparse
import json
from pathlib import Path
from finocr_qualification.evidence import export_evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(export_evidence(args.root,args.archive),indent=2));return 0
    except Exception as exc:
        print(json.dumps({'status':'export_failed','error':str(exc),'inference_executed':0},indent=2));return 2


if __name__=='__main__':raise SystemExit(main())
