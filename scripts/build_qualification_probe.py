"""Compile the standalone schema converter offline with an existing compiler."""
import argparse
import json
from pathlib import Path
from finocr_qualification.probe import build_probe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llama-source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compiler',default='clang++')
    args=parser.parse_args()
    try:
        result=build_probe(Path(__file__).resolve().parents[1],args.llama_source,args.output,args.compiler)
        print(json.dumps(result,indent=2));return 0
    except Exception as exc:
        print(json.dumps({'status':'offline_probe_build_failed','error':str(exc),'inference_executed':0},indent=2));return 2


if __name__=='__main__':raise SystemExit(main())
