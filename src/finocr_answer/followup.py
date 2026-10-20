"""Historical v2 ticket format. Preparation is paused; no new allowance exists."""
from __future__ import annotations
import hashlib
from pathlib import Path
from .audit import audit_original, snapshot
from .backend import EXECUTION
from .historical_contract_v2 import VERSION, CONTRACT_VERSION, INSTRUCTION, SCHEMA, digest, strict_json
from .pause import require_inference_authorized
from .setup import identity, runtime, sha, source_identity, verify_assets
from finocr.io import write_json

BUDGET={'campaign_id':'synthetic-contract-v2','additional_requests':6,'max_campaigns':1,
        'previous_requests':6,'cumulative_synthetic_request_ceiling':12,'primary_requests':0,
        'annotated_page_requests':0,'retry_policy':'none; transport attempts are charged before submission'}


def followup_root(assets:Path) -> Path:
    return assets.resolve().parent/'followups'/'synthetic-contract-v2'


def require_lineage(setup:dict) -> None:
    lineage=setup['lineage']
    actual=snapshot(Path(lineage['run_path']),Path(lineage['setup_path']),Path(lineage['campaign_path']))
    if actual!=lineage['snapshot']:raise ValueError('Original run/setup/campaign changed; preserve and inspect')


def prepare_followup(previous_setup:Path,previous_campaign:Path,previous_run:Path,repository:Path) -> dict:
    require_inference_authorized()  # no new seal, ticket, cache or allowance
    previous_setup,previous_campaign,previous_run=(p.resolve() for p in (previous_setup,previous_campaign,previous_run))
    audit=audit_original(previous_run,previous_setup,previous_campaign)
    old=strict_json(previous_setup.read_text());assets=Path(old['asset_root']).resolve();output=followup_root(assets)
    if output.exists():raise FileExistsError('The single v2 follow-up already exists; never reset its setup or ledger')
    if runtime()!=old['runtime']:raise ValueError('Reuse the exact existing .venv-answer; runtime changed')
    verify_assets(old['lock'],assets)
    if identity(Path(old['model']['path']))!=old['model'] or identity(Path(old['server']['path']))!=old['server']:
        raise ValueError('Model/backend bytes changed')
    if sha(assets/'converted/conversion.json')!=old['conversion_sha256']:raise ValueError('Conversion record changed')
    if old['instruction_sha256']!=hashlib.sha256(INSTRUCTION.encode()).hexdigest():raise ValueError('Synthetic instruction changed; prompt tuning is not included')
    result={**old,'version':VERSION,'contract_version':CONTRACT_VERSION,'schema_sha256':digest(SCHEMA),
            'source_sha256':source_identity(repository),'execution':EXECUTION,'budget':BUDGET,
            'control_prompts':audit['control_prompts'],'campaign_root':str(output),'cache_root':str(output/'cache'),
            'lineage':{'setup_path':str(previous_setup),'campaign_path':str(previous_campaign),'run_path':str(previous_run),
                       'snapshot':audit['preservation']['snapshot']},
            'changes':['Stricter typed JSON grammar and response validation; no output repair',
                       'Flash Attention explicitly disabled and verified before inference'],
            'benchmark_generation_enabled':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir() # exclusive single follow-up ticket
    write_json(output/'predecessor-audit.json',audit)
    write_json(output/'setup_manifest.json',result)
    return {'kind':'followup_preparation_only','setup':str(output/'setup_manifest.json'),
            'additional_inference_budget':6,'inference_executed':False,'original_artifacts_unchanged':True}


def validate_followup_setup(setup:dict,setup_path:Path,output:Path) -> None:
    root=followup_root(Path(setup['asset_root']))
    if setup_path.resolve()!=root/'setup_manifest.json' or Path(setup.get('campaign_root','')).resolve()!=root:
        raise ValueError('Use the single fixed v2 follow-up setup, not a copied budget ticket')
    if output.resolve()!=root/'run':raise ValueError('Use the fixed v2 run directory; no alternate campaign paths')
    if Path(setup.get('cache_root','')).resolve()!=root/'cache':raise ValueError('Use the isolated v2 cache; original cache is read-only')
    if setup.get('budget')!=BUDGET or setup.get('execution')!=EXECUTION:raise ValueError('Frozen follow-up budget/execution changed')
    if setup.get('schema_sha256')!=digest(SCHEMA) or setup.get('instruction_sha256')!=hashlib.sha256(INSTRUCTION.encode()).hexdigest():
        raise ValueError('Follow-up contract differs from current validation code')
    require_lineage(setup)
