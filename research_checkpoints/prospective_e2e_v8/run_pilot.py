"""Locked end-to-end pilot v8: offline by default; --run sends bounded Azure calls."""
import argparse
import base64
import datetime
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile

from io_utils import read,write,digest,require
from integrated_processing import postprocess, strict_contract
from output_contract import SYSTEM, CONDITION, RESPONSE_FORMAT

ROOT=Path(__file__).resolve().parent
ARMS=('retrieved_text','retrieved_image','oracle_image','empty_context')
EXPECTED='gpt-5-mini-2025-08-07'

def endpoint_url(value):
    u=urlsplit(value.strip());host=u.hostname or ''
    allowed=host.endswith('.openai.azure.com') or host.endswith('.services.ai.azure.com')
    require(u.scheme=='https' and allowed and not any([u.username,u.password,u.query,u.fragment,u.port]),'Use a plain HTTPS Azure resource endpoint, without credentials/query/project path')
    require(u.path.rstrip('/') in ['','/openai','/openai/v1','/openai/v1/chat/completions','/openai/v1/responses'],'Unsupported endpoint path; use Azure resource endpoint')
    return 'https://'+host+'/openai/v1/chat/completions'

def validate_bundle():
    lock=read(ROOT/'study_lock.json')
    for name,h in lock['sha256'].items():
        p=(ROOT/name).resolve()
        require(ROOT in p.parents and digest(p.read_bytes())==h,'Frozen file changed: '+name)
    cases=read(ROOT/'prepared/cases.json');assets=read(ROOT/'prepared/page_assets.json')
    queries={q['case_id']:q for q in read(ROOT/'prepared/queries.json')}
    rankings=read(ROOT/'provenance/rankings.json')
    keys=set()
    for c in cases:
        key=c['case_id'],c['arm'];require(key not in keys,'Duplicate condition');keys.add(key)
        require(c['arm'] in ARMS,'Invalid arm')
        require(c['prompt_condition']==CONDITION,'Prompt condition mismatch')
        require(c['question']==queries[c['case_id']]['question'] and c['task_id']==queries[c['case_id']]['task_id'] and c['doc_id']==queries[c['case_id']]['doc_id'],'Benchmark question identity changed')
        require(len(c['page_assets'])==len(set(c['page_assets'])),'Duplicate supplied page')
        pages=[assets[k]['pdf_page_index'] for k in c['page_assets']]
        require(pages==sorted(pages),'Presentation pages must be in physical index order')
        require(all(assets[k]['doc_id']==c['doc_id'] for k in c['page_assets']),'Cross-document asset')
        if c['arm'] in ['retrieved_text','retrieved_image']:
            require(pages==rankings[c['case_id']]['selected_pages'],'Retrieved arm pages changed')
        if c['arm']=='empty_context':require(not c['page_assets'],'Empty-context control has evidence')
    require(len(cases)==16 and len(queries)==4,'Pilot must have 4 questions and 16 conditions')
    specs=read(ROOT/'calculation_registry.json')['specifications'];metrics=read(ROOT/'table_roles.json')['roles']
    for cid in queries:require({r['name'] for r in specs[cid]['roles']}==set(metrics[cid]),'Role registry mismatch')
    return cases,assets

def payload(case,assets,deployment):
    content=[{'type':'text','text':'Benchmark question (unchanged): '+case['question']+'\nFixed clarification: '+case['clarification']}]
    for key in case['page_assets']:
        a=assets[key]
        content.append({'type':'text','text':'Source document '+a['doc_id'].split(':',1)[1]+'; zero-based PDF page index '+str(a['pdf_page_index'])+'.'})
        if case['arm']=='retrieved_text':
            content.append({'type':'text','text':'Native page text:\n'+(ROOT/'prepared'/a['text']).read_text(encoding='utf-8')})
        else:
            data=base64.b64encode((ROOT/'prepared'/a['image']).read_bytes()).decode('ascii')
            content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+data,'detail':'high'}})
    if not case['page_assets']:content.append({'type':'text','text':'No source pages were supplied. Use the missing-evidence abstention rule.'})
    return {'model':deployment,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':content}],
            'response_format':RESPONSE_FORMAT,'max_completion_tokens':4096,'reasoning_effort':'low'}

def eligible(m):
    return (m.get('status')=='response_saved' and m.get('http_status')==200 and m.get('returned_model')==EXPECTED
            and m.get('finish_reason')=='stop' and bool(m.get('answer_characters'))
            and m.get('estimated_usd') is not None and m.get('strict_response_contract_validated') is True and m.get('postprocessing_complete') is True)

def execute(cases,assets,out,url,key,deployment,input_rate,output_rate,max_new,stop_after):
    records=[read(f) for f in sorted(out.glob('*/attempt-*/result.json'))]
    require(all(eligible(m) for m in records),'Prior uncertain/error/capped/drift/schema-failed attempt exists. Inspect it; no automatic retry.')
    spent=sum(m['estimated_usd'] for m in records)
    require(len(records)<=16,'Request limit exceeded')
    count=0;halted=False
    lock=out/'.runner-active'
    with lock.open('x',encoding='utf-8') as f:f.write('One process only. If interrupted, inspect attempts before removing this stale marker.')
    try:
        for c in cases:
            condition=out/(c['case_id']+'-'+c['arm'])
            body=json.dumps(payload(c,assets,deployment),ensure_ascii=False,separators=(',',':')).encode()
            request_sha=digest(body)
            old=list(condition.glob('attempt-*/result.json'))
            if old:
                require(len(old)==1 and read(old[0])['request_sha256']==request_sha,'Cached request changed')
                require((old[0].parent/'postprocessed.json').is_file(),'Cached postprocessing missing')
                continue
            if count>=max_new or len(records)+count>=16 or spent>=stop_after:break
            folder=condition/'attempt-01';folder.mkdir(parents=True,exist_ok=False)
            meta={'case_id':c['case_id'],'task_id':c['task_id'],'doc_id':c['doc_id'],'arm':c['arm'],
                  'supplied_pages':[assets[k]['pdf_page_index'] for k in c['page_assets']],
                  'request_sha256':request_sha,'status':'in_progress','estimated_usd':None,'automatic_retries':0,
                  'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'postprocessing_complete':False}
            write(folder/'result.json',meta);count+=1;started=time.perf_counter()
            print('Sending',c['case_id'],c['arm'],flush=True)
            try:
                req=urllib.request.Request(url,data=body,headers={'api-key':key,'Content-Type':'application/json'},method='POST')
                with urllib.request.urlopen(req,timeout=120) as response:
                    response_bytes=response.read();meta['http_status']=response.status
                (folder/'response.json').write_bytes(response_bytes)
                api=json.loads(response_bytes);choice=api.get('choices',[{}])[0]
                text=choice.get('message',{}).get('content') or ''
                (folder/'answer.txt').write_bytes(text.encode('utf-8'))
                usage=api.get('usage',{});pt=usage.get('prompt_tokens');ct=usage.get('completion_tokens')
                cost=(pt*input_rate+ct*output_rate)/1e6 if type(pt) is int and type(ct) is int and pt>=0 and ct>=0 else None
                meta.update(status='response_saved',returned_model=api.get('model'),finish_reason=choice.get('finish_reason'),
                            usage=usage,estimated_usd=cost,answer_characters=len(text))
                if cost is not None:spent+=cost
                processed=postprocess(text,c,assets,ROOT/'prepared')
                write(folder/'postprocessed.json',processed)
                meta.update(postprocessing_complete=True,strict_response_contract_validated=strict_contract(text),schema_issues=processed['schema_issues'],
                            release_status=processed['evidence_gate']['release_status'],
                            calculator_status=processed['calculator_result']['status'],source_verified=False)
            except urllib.error.HTTPError as exc:
                meta.update(status='http_error',http_status=exc.code,error='No automatic retry; billing may be uncertain')
            except Exception as exc:
                meta.update(status='request_or_processing_error',error_type=type(exc).__name__,error='No automatic retry; preserve this attempt for inspection')
            meta['wall_seconds']=time.perf_counter()-started;write(folder/'result.json',meta)
            print(json.dumps({k:meta.get(k) for k in ['case_id','arm','status','finish_reason','release_status','calculator_status','estimated_usd']}),flush=True)
            if not eligible(meta):halted=True;break
    finally:
        lock.unlink()
    return {'new_requests':count,'recorded_attempts_in_policy':len(records)+count,'observed_estimated_usd':spent,
            'halted_on_error_or_uncertain_outcome':halted,'results_directory':str(out.resolve()),
            'cost_stop':'Observed-cost soft stop; current call may overshoot. Not a subscription spending limit.'}

def zip_latest(output):
    output=Path(output).resolve();name=(output/'latest_run.txt').read_text(encoding='utf-8').strip();run=(output/name).resolve()
    require(output in run.parents and (run/'policy.json').is_file(),'Invalid latest-run pointer')
    dest=Path.home()/'Downloads';dest.mkdir(parents=True,exist_ok=True)
    target=dest/('prospective-e2e-v8-review-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip')
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT/'study_lock.json','study_lock.json')
        for f in sorted(run.rglob('*')):
            if f.is_file():z.write(f,(Path(run.name)/f.relative_to(run)).as_posix())
    print('ZIP:',target)
    return target

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    action=ap.add_mutually_exclusive_group();action.add_argument('--check',action='store_true');action.add_argument('--run',action='store_true');action.add_argument('--zip-latest',action='store_true')
    ap.add_argument('--output',type=Path,default=Path.home()/'financial-ocr-data'/'audits'/'prospective-e2e-v8')
    ap.add_argument('--case');ap.add_argument('--arm',choices=ARMS);ap.add_argument('--max-new',type=int,default=1)
    ap.add_argument('--input-rate',type=float);ap.add_argument('--output-rate',type=float);ap.add_argument('--stop-after-usd',type=float,default=1)
    args=ap.parse_args();cases,assets=validate_bundle()
    if args.zip_latest:zip_latest(args.output);return
    deployment=os.environ.get('AZURE_VISION_DEPLOYMENT','');endpoint=os.environ.get('AZURE_VISION_ENDPOINT','')
    key=os.environ.get('AZURE_VISION_API_KEY') or os.environ.get('AZURE_OPENAI_API_KEY','')
    print(json.dumps({'asset_check':'passed','questions':4,'planned_conditions':16,'request_limit':16,
                     'endpoint_set':bool(endpoint),'key_set':bool(key),'deployment':deployment or None,
                     'expected_model':EXPECTED,'network_requests':'explicit --run enabled' if args.run else 0,
                     'source_verified':False,'response_format':'json_schema','strict_schema':True,'prompt_condition':CONDITION},indent=2))
    if not args.run:return
    require(1<=args.max_new<=16,'max-new must be 1..16')
    require(all(x is not None and math.isfinite(x) and x>0 for x in [args.input_rate,args.output_rate,args.stop_after_usd]),'Supply current positive finite input/output rates (USD per million tokens) and cost cap')
    require(deployment=='gpt-5-mini-1' and endpoint and key,'Use frozen deployment gpt-5-mini-1 and load private endpoint/key in this session')
    require(args.input_rate==0.25 and args.output_rate==2.0 and args.stop_after_usd<=1.0,'Frozen budget uses input 0.25/output 2.00 USD per million and a maximum $1 soft cap; changed offer requires a separate registration')
    if args.case:require(args.case in {c['case_id'] for c in cases},'Unknown case')
    chosen=[c for c in cases if (not args.case or c['case_id']==args.case) and (not args.arm or c['arm']==args.arm)]
    require(chosen,'No selected conditions');url=endpoint_url(endpoint)
    policy={'version':'prospective-e2e-v8','operational_completion':'typed fully received outcomes remain complete when grounding is held; no retries','study_lock_sha256':digest((ROOT/'study_lock.json').read_bytes()),
            'deployment':deployment,'expected_model':EXPECTED,'endpoint_sha256':digest(url.encode()),
            'input_rate':args.input_rate,'output_rate':args.output_rate,'stop_after_usd':args.stop_after_usd,
            'rates_unit':'USD per million tokens; cached input charged at full input rate in estimate; reasoning included in completion count',
            'system_sha256':digest(SYSTEM.encode()),'response_format_sha256':digest(json.dumps(RESPONSE_FORMAT,sort_keys=True).encode()),'settings':{'max_completion_tokens':4096,'reasoning_effort':'low','image_detail':'high'},
            'request_limit':16,'automatic_retries':0,'prompt_condition':CONDITION}
    identity=digest(json.dumps(policy,sort_keys=True).encode())[:12]
    args.output.mkdir(parents=True,exist_ok=True)
    pointer=args.output/'latest_run.txt'
    if pointer.exists():require(pointer.read_text(encoding='utf-8').strip()==identity,'Pilot policy changed; preserve existing attempts instead of starting another policy')
    out=args.output/identity;out.mkdir(parents=True,exist_ok=True)
    if (out/'policy.json').exists():require(read(out/'policy.json')==policy,'Existing run policy changed')
    else:write(out/'policy.json',policy)
    (args.output/'latest_run.txt').write_text(identity,encoding='utf-8')
    result=execute(chosen,assets,out,url,key,deployment,args.input_rate,args.output_rate,args.max_new,args.stop_after_usd)
    print(json.dumps(result,indent=2))
    if result['halted_on_error_or_uncertain_outcome']:raise SystemExit(2)

if __name__=='__main__':
    main()
