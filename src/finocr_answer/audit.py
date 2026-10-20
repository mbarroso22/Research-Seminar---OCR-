"""Read-only audit of the six saved v1 requests. Never loads a model or submits work."""
from __future__ import annotations
import csv
import hashlib
import json
import re
from pathlib import Path
from .backend import observe_settings
from .historical_contract_v2 import canonical, digest, strict_json
from .feasibility import parse_stream
from .setup import sha
from .synthetic import historical_cases_v2 as cases
from .historical_validation_v2 import functional_checks
from finocr.io import write_json

LEGACY_SCHEMA_SHA='7dbcb454549549440b0254292bc30cea0fd3192bc2aa5e249ec1d754939dd8d7'
LEGACY_INSTRUCTION_SHA='8ba2802f2dfc37c1ebc829bd71fd17069bba2ef21ae269f5f8e61ea149e8046d'
CASES=tuple(c['task_id'].split(':')[1] for c in cases())


def snapshot(run: Path,setup: Path,campaign: Path) -> dict:
    return {'setup':sha(setup),'campaign':sha(campaign),
            'run':{p.relative_to(run).as_posix():sha(p) for p in sorted(run.rglob('*')) if p.is_file()}}


def packed_pages(prompt: str) -> dict[int,str]:
    if '<|im_end|>' not in prompt: raise ValueError('Expected the pinned Qwen template')
    body=prompt.rsplit('<|im_end|>',1)[0]
    positions=list(re.finditer(r'\[p=(\d+)\]\n',body));pages={}
    for index,match in enumerate(positions):
        page=int(match.group(1))
        if page in pages:raise ValueError('Duplicate page header')
        end=positions[index+1].start() if index+1<len(positions) else len(body)
        text=body[match.end():end].removesuffix('\n')
        if text=='[blank]':text=''
        pages[page]=text.removesuffix('\n[truncated]')
    if list(pages)!=list(range(5)):raise ValueError('Expected all five original zero-based candidates')
    return pages


def resource_audit(run: Path,manifest: dict) -> dict:
    samples=[strict_json(line) for line in (run/'memory_samples.jsonl').read_text().splitlines() if line]
    if not samples:raise ValueError('No resource samples')
    gpu=[]
    for row in samples:
        if 'gpu_device_wide' in row:
            values=list(csv.reader(row['gpu_device_wide'].splitlines()))
            if len(values)!=1 or 'RTX 3070 Ti' not in values[0][1]:raise ValueError('Unexpected sampled device')
            gpu.append(int(values[0][-1].strip()))
    recomputed={'sample_count':len(samples),'server_sampled_peak_rss_bytes':max(s['server_rss_bytes'] for s in samples),
                'client_sampled_peak_rss_bytes':max(s['client_rss_bytes'] for s in samples),
                'sampled_peak_sum_rss_bytes':max(s['server_rss_bytes']+s['client_rss_bytes'] for s in samples),
                'minimum_system_available_bytes':min(s['system_available_bytes'] for s in samples),
                'sampled_peak_system_used_bytes':max(s['system_total_bytes']-s['system_available_bytes'] for s in samples),
                'device_wide_sampled_peak_used_mib':max(gpu) if gpu else None}
    if any(manifest['memory'].get(k)!=v for k,v in recomputed.items()):raise ValueError('Recorded resource summary does not reconcile')
    if manifest['memory'].get('measurement_errors') or not gpu:raise ValueError('Resource collection failed')
    return {'recomputed':recomputed,'summary_matches_samples':True,'scope':'Sampled RSS / whole-system used RAM / whole-device VRAM. Not isolated exact peaks.',
            'windows_peak_working_set':'Recorded summary only; no per-sample OS peak values supplied.'}


def audit_original(run: Path,setup_path: Path,campaign_path: Path) -> dict:
    run,setup_path,campaign_path=(p.resolve() for p in (run,setup_path,campaign_path))
    before=snapshot(run,setup_path,campaign_path)
    setup=strict_json(setup_path.read_text());campaign=strict_json(campaign_path.read_text());manifest=strict_json((run/'run_manifest.json').read_text())
    def require(condition,message):
        if not condition:raise ValueError(message)
    require(setup['version']=='bounded-answer-preparation-v1','Expected original v1 setup')
    require(setup['schema_sha256']==LEGACY_SCHEMA_SHA and setup['instruction_sha256']==LEGACY_INSTRUCTION_SHA,'Unexpected original schema/instruction')
    require(manifest['kind']=='synthetic_feasibility_only' and manifest['primary_requests']==0 and manifest['annotated_page_requests']==0 and manifest['benchmark_generation_enabled'] is False,'Not the original synthetic-only scope')
    require(manifest['setup']['sha256']==before['setup']==campaign['setup_sha256'],'Original setup/hash lineage mismatch')
    require(manifest['request_budget']==6 and manifest['attempted']==campaign['attempted']==len(manifest['records'])==6,'Six-request ledger does not reconcile')
    records={r['case_id']:r for r in manifest['records']};require(set(records)==set(CASES),'Unexpected case IDs')
    results=[];controls={}
    for case in cases():
        name=case['task_id'].split(':')[1];record=records[name];root=run/name
        request=strict_json((root/'request.json').read_text());packing=strict_json((root/'packing.json').read_text())
        prompt=(root/'prompt.txt').read_bytes().decode('utf-8')
        require(packing['prompt']==prompt and packing['token_ids']==request['prompt'],'Prompt/token identity mismatch: '+name)
        require(len(request['prompt'])==packing['input_tokens']==record['input_tokens'],'Input token count mismatch: '+name)
        require(request['n_predict']==1024 and request['cache_prompt'] is False and digest(request['json_schema'])==LEGACY_SCHEMA_SHA,'Original decoder/schema mismatch: '+name)
        request_hash=digest({'model':setup['model']['sha256'],'instruction':setup['instruction_sha256'],'schema':setup['schema_sha256'],
                             'backend':setup['server']['sha256'],'setup_sha256':before['setup'],'request':request})
        require(request_hash==record['request_sha256']==campaign['requests'][CASES.index(name)],'Canonical request/ledger hash mismatch: '+name)
        decoder={'n_predict':1024,'temperature':0,'seed':0,'top_k':1,'top_p':1.0,'min_p':0.0,'repeat_penalty':1.0,
                 'presence_penalty':0.0,'frequency_penalty':0.0,'cache_prompt':False,'stream':True,'id_slot':0}
        require(set(request)==set(decoder)|{'prompt','json_schema'} and all(request[k]==v for k,v in decoder.items()),'Original decoder/allowlist changed: '+name)
        require(packing['input_tokens']<=5120 and packing['evidence_tokens']<=4096 and packing['overhead_tokens']<=1024,'Original input/evidence budget mismatch: '+name)
        require([p['page_id'] for p in packing['retained']]==list(range(5)) and all(0<=p['retained_interval'][1]<=800 for p in packing['retained']),'Original page prefix budget mismatch: '+name)
        if name=='capacity':require(packing['input_tokens']==5120 and packing['evidence_tokens']==4096 and packing['overhead_tokens']==1024,'Original maximum-capacity case missing')
        raw=(root/'raw-response.sse').read_bytes();require(hashlib.sha256(raw).hexdigest()==record['response_sha256'],'Raw response hash mismatch: '+name)
        content,final=parse_stream(raw)
        require(content==(root/'raw-content.txt').read_bytes().decode('utf-8'),'SSE/raw content mismatch: '+name)
        require(final==strict_json((root/'backend-final.json').read_text()),'Terminal response mismatch: '+name)
        parsed=strict_json(content);require(parsed==strict_json((root/'parsed.json').read_text()),'Parsed response mismatch: '+name)
        require(final['tokens_predicted']==record['generated_tokens']==final['timings']['predicted_n'] and final['timings']['prompt_n']==len(request['prompt']),'Backend token/timing mismatch: '+name)
        require(not final.get('truncated') and final.get('stop_type')!='limit' and 0<final['tokens_predicted']<=1024,'Failed/truncated original completion: '+name)
        pages=packed_pages(prompt)
        for page,text in pages.items():require(case['pages'][page]['raw_text'].startswith(text),'Source-prefix mismatch: '+name)
        checks=functional_checks(parsed,name,pages)
        results.append({'case_id':name,'historical_checks':record['checks'],'strict_v2_checks':checks,'request_sha256':request_hash,
                        'prompt_sha256':sha(root/'prompt.txt'),'response_sha256':record['response_sha256'],'input_tokens':record['input_tokens'],
                        'generated_tokens':record['generated_tokens'],'recorded_wall_seconds':record['wall_seconds']})
        controls[name]={'prompt_sha256':sha(root/'prompt.txt'),'token_ids_sha256':digest(request['prompt'])}
    resources=resource_audit(run,manifest)
    observed=observe_settings((run/'server.stderr.log').read_text())
    unchanged=before==snapshot(run,setup_path,campaign_path);require(unchanged,'Original artifacts changed during read-only audit')
    return {'kind':'read_only_synthetic_v1_artifact_audit','integrity_verified':True,'preservation':{'unchanged':unchanged,'snapshot':before},
            'original_requests':6,'additional_inference_requests':0,'primary_requests':0,'annotated_page_requests':0,
            'runtime_observed':observed,'intended_flash_attention':'disabled',
            'intended_flash_attention_reproduced':observed['flash_attention_declared']==observed['flash_attention_effective']=='disabled',
            'resources':resources,'recorded_startup_seconds':manifest['startup_wall_seconds'],'recorded_total_wall_seconds':manifest['wall_seconds'],
            'cases':results,'control_prompts':controls,'strict_mechanical_pass_count':sum(r['strict_v2_checks']['mechanical_pass'] for r in results),
            'feasibility':'Output contract/support failures remain; resource success under FA-enabled execution is not a pass of the intended FA-off condition.',
            'limits':'No model/backend/weight bytes or conversion/acquisition records supplied in the review bundle; their identities are recorded, not independently rehashed here. No benchmark accuracy measured.'}


def audit_to_directory(run: Path,setup: Path,campaign: Path,output: Path) -> dict:
    output=output.resolve()
    for protected in [run.resolve(),setup.resolve().parent,campaign.resolve().parent]:
        if output==protected or protected in output.parents or output in protected.parents:raise ValueError('Audit output must be outside original run/assets')
    if output.exists():raise FileExistsError('Audit output exists; preserve the prior review')
    report=audit_original(run,setup,campaign)
    output.mkdir(parents=True)
    write_json(output/'audit.json',report)
    return report
