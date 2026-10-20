"""Qualification dispatch; absent separately reviewed external approval, paused.

This command cannot issue/install approval, grant attempts, or change settings.
"""
import argparse
import json
from pathlib import Path
from finocr_answer.pause import InferencePausedError
from finocr_qualification.runner import run
from finocr_qualification.authorization import AuthorizationRejected


def result_exit_code(result):
    """Zero means automated checks completed, never human-qualified correctness."""
    if result.get('export_error') or result.get('cleanup_error'):
        return 7
    if result.get('status') not in {'completed_manual_review_pending',
            'completed_mechanical_failures_manual_review_pending','terminal_stop'}:
        return 1
    if result.get('export',{}).get('verified') is not True:
        return 7
    if result.get('status') == 'completed_manual_review_pending' and result.get('automated_checks_pass') is True:
        return 0
    if result.get('status') == 'completed_mechanical_failures_manual_review_pending':
        return 6
    if result.get('status') == 'terminal_stop':
        return 5
    return 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    parser.add_argument('--authorization',type=Path,
        help='Existing separately reviewed record at the fixed approval location; not an enable switch')
    args=parser.parse_args()
    try:
        result=run(args.preparation,Path(__file__).resolve().parents[1],args.authorization)
    except InferencePausedError as exc:
        print(json.dumps({'status':'inference_paused','inference_executed':0,
            'additional_inference_authorized':0,'remaining_authorized_requests':0,'reason':str(exc)},indent=2))
        return 2
    except AuthorizationRejected as exc:
        print(json.dumps({'status':'authorization_rejected','completion_attempts_this_invocation':0,
            'campaign_created_this_invocation':False,'reason':str(exc)},indent=2))
        return 3
    except Exception as exc:
        # Evidence-write errors may occur after a charged attempt. Never print a
        # fabricated zero-inference count; preserve and inspect the fixed anchor.
        print(json.dumps({'status':'qualification_error','error':f'{type(exc).__name__}: {exc}',
            'attempt_count':'inspect_preserved_campaign_evidence'},indent=2))
        return 1
    print(json.dumps(result,indent=2))
    return result_exit_code(result)


if __name__=='__main__':raise SystemExit(main())
