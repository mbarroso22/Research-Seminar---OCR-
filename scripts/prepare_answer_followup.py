"""Follow-up preparation is paused; no new inference ticket or allowance."""
import argparse
import json
from pathlib import Path
from finocr_answer.followup import prepare_followup
from finocr_answer.pause import InferencePausedError


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous-setup',type=Path,required=True)
    p.add_argument('--previous-campaign',type=Path,required=True)
    p.add_argument('--previous-run',type=Path,required=True)
    a=p.parse_args()
    try:r=prepare_followup(a.previous_setup,a.previous_campaign,a.previous_run,Path(__file__).resolve().parents[1])
    except InferencePausedError as exc:
        print(json.dumps({'status':'inference_paused','inference_executed':0,'additional_inference_authorized':0,'error':str(exc)},indent=2))
        return 2
    print(json.dumps(r,indent=2))


if __name__=='__main__':raise SystemExit(main())
