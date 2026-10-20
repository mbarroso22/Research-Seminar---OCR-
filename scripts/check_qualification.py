"""Offline qualification preparation only. Never launches a model or grants requests."""
import argparse
import json
from pathlib import Path
from finocr_qualification.preparation import prepare_offline


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['v2-setup','contract-review','llama-source','native-build','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--preserve',type=Path,nargs='+',default=[])
    parser.add_argument('--original-preservation-set',type=Path,required=True,
        help='Untouched reviewed before/preserved-hashes.txt (184 files)')
    parser.add_argument('--preservation-closeout',type=Path,required=True,
        help='Separately named successful final preservation closeout directory')
    args=parser.parse_args()
    try:
        report=prepare_offline(Path(__file__).resolve().parents[1],args.v2_setup,args.contract_review,
            args.llama_source,args.native_build,args.output,preserve=args.preserve,
            original_preservation_set=args.original_preservation_set,
            preservation_closeout=args.preservation_closeout)
        print(json.dumps({k:report[k] for k in ['kind','status','inference_executed',
            'additional_inference_authorized','remaining_authorized_requests','preservation_pass']},indent=2))
        return 0 if report['status']=='offline_ready_for_separate_review_not_authorization' else 2
    except Exception as exc:
        print(json.dumps({'status':'offline_preflight_failed','error':str(exc),'inference_executed':0,
            'additional_inference_authorized':0,'remaining_authorized_requests':0},indent=2))
        return 2


if __name__=='__main__':raise SystemExit(main())
