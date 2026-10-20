"""Offline source/hash/response audit only; zero inference requests."""
import argparse
import json
from pathlib import Path
from finocr_answer.audit import audit_to_directory


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['run-dir','setup','campaign','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit_to_directory(a.run_dir,a.setup,a.campaign,a.output)
    print(json.dumps({k:r[k] for k in ['integrity_verified','additional_inference_requests','strict_mechanical_pass_count','intended_flash_attention_reproduced']},indent=2))
    return 0 # integrity audit succeeded, not a model-feasibility pass


if __name__=='__main__':raise SystemExit(main())
