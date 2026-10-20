"""Zero-inference contract gate. Writes review artifacts, never campaign artifacts."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from .contract import CONTRACT_VERSION, INSTRUCTION, SCHEMA, canonical, digest, strict_json, wire
from .conformance_fixtures import positives, negatives, pages
from .grammar import Grammar
from .synthetic import CASE_VERSION, cases, pack, historical_cases_v2, pack_historical_v2
from .validation import functional_checks
from .setup import sha, source_identity

PINNED_COMMIT='a7a98e0fffed794396b3fbad4dcdbbc184963645'
CONVERTER_LF_SHA256='1f6fee46d14f0b66f9e4150da8b17485534e544503d7898e72a4ebf1d3ed9c1d'


def file_snapshot(paths):
    result={}
    for path in paths:
        p=path.resolve()
        if not p.exists():raise FileNotFoundError('Required preservation path missing: '+str(p))
        if p.is_dir():result[str(p)]={q.relative_to(p).as_posix():sha(q) for q in sorted(p.rglob('*')) if q.is_file()}
        else:result[str(p)]=sha(p)
    return result


def compile_schema(source: Path, schema: Path) -> bytes:
    script=source/'examples/json_schema_to_grammar.py'
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit!=PINNED_COMMIT:raise ValueError('Use the existing pinned llama.cpp b6500 checkout')
    normalized=hashlib.sha256(script.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    if normalized!=CONVERTER_LF_SHA256:raise ValueError('Pinned converter source changed')
    # -X utf8 covers the converter's file open() as well as its stdout on Windows.
    result=subprocess.run([sys.executable,'-X','utf8',str(script),str(schema)],
        env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,timeout=30)
    if result.returncode or result.stderr.strip():raise ValueError('Schema conversion failed or warned: '+result.stderr.decode('utf-8',errors='replace'))
    # Python stdout can use CRLF on Windows. Normalize rule separators only;
    # escaped CR/LF terminals remain unchanged and the grammar matches C++ output.
    return result.stdout.replace(b'\r\n',b'\n')


def tokenizer_checks(tokenizer, *, historical_run: Path | None=None):
    records=[]
    if historical_run is not None:
        for case in historical_cases_v2():
            name=case['task_id'].split(':')[1];old=historical_run/name
            _,packed=pack_historical_v2(case,tokenizer)
            if packed['prompt'].encode()!=(old/'prompt.txt').read_bytes() or packed['token_ids']!=strict_json((old/'request.json').read_text(encoding='utf-8'))['prompt']:
                raise ValueError('Historical tokenizer/template parity failed; preserve original outputs')
    for case in cases():
        name=case['task_id'].split(':')[1];_,packed=pack(case,tokenizer)
        if name=='capacity' and (packed['input_tokens']!=5120 or packed['evidence_tokens']!=4096 or packed['overhead_tokens']!=1024):
            raise ValueError('Revised capacity must exercise the exact original budgets')
        records.append({'case_id':name,'input_tokens':packed['input_tokens'],'evidence_tokens':packed['evidence_tokens'],
            'overhead_tokens':packed['overhead_tokens'],'body_tokens':[p['retained_interval'][1] for p in packed['retained']],
            'page_ids':[p['page_id'] for p in packed['retained']],
            'prompt_sha256':hashlib.sha256(packed['prompt'].encode()).hexdigest(),'token_ids_sha256':digest(packed['token_ids'])})
    return {'kind':'local_tokenization_only_no_generation','historical_token_parity_checked':historical_run is not None,'cases':records}


def load_local_tokenizer(repository: Path, root: Path, *, historical_run=None):
    """Read pinned tokenizer/config files only; never open weight/model files."""
    from importlib.metadata import version
    lock=strict_json((repository/'docs/ANSWER_SETUP_LOCK.json').read_text(encoding='utf-8'))
    expected={f['name']:f['sha256'] for f in lock['model_files']}
    hashes={}
    for name in ['config.json','tokenizer_config.json','vocab.json','merges.txt','tokenizer.json']:
        path=root/name
        if name=='tokenizer.json' and not path.exists():
            if historical_run is None:raise ValueError('Missing tokenizer.json requires exact historical token parity')
            continue
        if sha(path)!=expected[name]:raise ValueError('Pinned tokenizer/config bytes differ: '+name)
        hashes[name]=sha(path)
    for package,wanted in [('transformers','4.56.2'),('tokenizers','0.22.2'),('Jinja2','3.1.6')]:
        if version(package)!=wanted:raise ValueError('Use the existing pinned answer environment: '+package)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(root,local_files_only=True,trust_remote_code=False)
    return tokenizer,{'files_verified':hashes,'rebuilt_from_pinned_vocab_merges':'tokenizer.json' not in hashes}


def run_offline(repository: Path, source: Path, output: Path, *, protected=(), read_only_roots=(), tokenizer=None, historical_run=None) -> dict:
    repository,source,output=(p.resolve() for p in (repository,source,output))
    for path in [repository,source,*protected,*read_only_roots]:
        p=path.resolve()
        if output==p or p in output.parents or output in p.parents:raise ValueError('Review output must be outside repository/source/protected paths')
    if output.exists():raise FileExistsError('Preserve the prior offline review')
    before=file_snapshot(protected)
    baseline=[repository/'docs/EXPANSION_V1_CONTROL.json',*sorted((repository/'src/finocr').rglob('*.py'))]
    baseline_before=file_snapshot(baseline)
    output.mkdir(parents=True)
    report={'kind':'offline_contract_conformance','contract_version':CONTRACT_VERSION,'case_version':CASE_VERSION,
        'inference_executed':0,'additional_inference_authorized':0,'remaining_authorized_requests':0,
        'historical_requests_spent':12,'benchmark_generation_enabled':False,
        'historical_results_recomputed_or_rewritten':False,'status':'checking',
        'source_sha256':source_identity(repository),'schema_canonical_sha256':digest(SCHEMA),
        'schema_wire_sha256':hashlib.sha256(wire(SCHEMA)).hexdigest(),
        'instruction_sha256':hashlib.sha256(INSTRUCTION.encode()).hexdigest(),'cases_sha256':digest(cases()),
        'semantic_support':'not_established_by_mechanical_fixtures'}
    try:
        (output/'schema-wire.json').write_bytes(wire(SCHEMA))
        # This envelope contains no prompt/decoder and is not a runnable completion request.
        (output/'schema-envelope.json').write_bytes(wire({'json_schema':SCHEMA}))
        (output/'instruction.txt').write_text(INSTRUCTION,encoding='utf-8')
        grammar_bytes=compile_schema(source,output/'schema-wire.json')
        (output/'schema.gbnf').write_bytes(grammar_bytes)
        grammar=Grammar(grammar_bytes.decode('utf-8'))
        report['grammar_sha256']=hashlib.sha256(grammar_bytes).hexdigest()
        report['converter']={'commit':PINNED_COMMIT,'lf_normalized_source_sha256':CONVERTER_LF_SHA256}
        checks=[]
        for name,value in positives().items():
            mechanics=functional_checks(value,name,pages(name))
            accepted=grammar.accepts(wire(value).decode())
            if not accepted or not mechanics['mechanical_pass']:raise ValueError('Handwritten positive failed: '+name)
            checks.append({'fixture':'handwritten_positive:'+name,'grammar_accepts':accepted,'mechanical_pass':True,
                           'model_output':False,'fully_supported_model_result':False})
        for label,name,value in negatives():
            mechanics=functional_checks(value,name,pages(name))
            if mechanics['mechanical_pass']:raise ValueError('Negative fixture incorrectly accepted: '+label)
            checks.append({'fixture':'constructed_negative:'+label,'grammar_accepts':grammar.accepts(wire(value).decode()),
                'mechanical_pass':False,'issues':mechanics['issues'],'model_output':False})
        report['fixture_checks']=checks
        report['tokenizer_check']=tokenizer_checks(tokenizer,historical_run=historical_run) if tokenizer is not None else {'status':'not_run','reason':'Provide the existing local tokenizer for the complete offline packing gate'}
        report['status']='offline_checks_pass' if tokenizer is not None else 'grammar_and_fixture_checks_pass_tokenizer_pending'
    except Exception as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            report['protected_artifacts_unchanged']=before==file_snapshot(protected)
            report['baseline_source_and_control_unchanged']=baseline_before==file_snapshot(baseline)
        except Exception as exc:
            report.update(protected_artifacts_unchanged=False,baseline_source_and_control_unchanged=False,
                          preservation_error=f'{type(exc).__name__}: {exc}')
        if not report['protected_artifacts_unchanged'] or not report['baseline_source_and_control_unchanged']:
            report['status']='failed_preservation'
        (output/'offline_conformance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if report['status']=='failed_preservation':raise ValueError('Protected artifacts changed; retain report and stop')
    return report
