"""Offline schema/grammar/fixture/tokenizer gate only. No inference or allowance."""
import argparse
import json
from pathlib import Path
from finocr_answer.conformance import load_local_tokenizer, run_offline


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--llama-source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tokenizer-root',type=Path)
    p.add_argument('--historical-v2-run',type=Path)
    p.add_argument('--preserve',type=Path,nargs='+',default=[])
    a=p.parse_args()
    if a.historical_v2_run and not a.tokenizer_root:p.error('--historical-v2-run requires --tokenizer-root')
    tokenizer=None;tokenizer_identity=None
    if a.tokenizer_root:
        tokenizer,tokenizer_identity=load_local_tokenizer(Path(__file__).resolve().parents[1],a.tokenizer_root,historical_run=a.historical_v2_run)
    protected=[*a.preserve,*([a.historical_v2_run] if a.historical_v2_run else [])]
    r=run_offline(Path(__file__).resolve().parents[1],a.llama_source,a.output,protected=protected,
                  read_only_roots=[a.tokenizer_root] if a.tokenizer_root else [],tokenizer=tokenizer,historical_run=a.historical_v2_run)
    if tokenizer_identity:
        r['tokenizer_identity']=tokenizer_identity
        (a.output/'offline_conformance.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:r[k] for k in ['kind','status','contract_version','inference_executed','additional_inference_authorized',
        'remaining_authorized_requests','protected_artifacts_unchanged','baseline_source_and_control_unchanged']},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
