"""Offline-only bindings and packing. This is neither a setup seal nor a ticket."""
from __future__ import annotations
import hashlib
from pathlib import Path
import subprocess
import time

from finocr_answer.contract import SCHEMA, INSTRUCTION, CONTRACT_VERSION, digest, wire, strict_json
from finocr_answer.conformance import load_local_tokenizer
from finocr_answer.setup import sha, runtime, tree, verify_assets
from finocr_answer.synthetic import CASE_VERSION, cases, pack
from finocr_answer.followup import require_lineage
from .evidence import snapshot, assert_preserved, write_bytes, write_json
from .probe import compare_native, sha_lf
from .resources import preflight_resources
from .preservation import preservation_extension

VERSION = 'qualification-runner-v2-offline-binding'
CAMPAIGN = 'synthetic-contract-v3-qualification'
REFERENCE_LF_SHA256 = 'b6d1611f7ed9714836b90b6f6d8ce9c9c41c2981af203903e8eb5048b67e793a'


def read_json(path):
    return strict_json(Path(path).read_text(encoding='utf-8-sig'))


def frozen_reference(repository: Path) -> dict:
    if sha_lf(repository/'docs/QUALIFICATION_FROZEN_IDENTITIES.json') != REFERENCE_LF_SHA256:
        raise ValueError('Frozen qualification reference changed')
    ref = read_json(repository/'docs/QUALIFICATION_FROZEN_IDENTITIES.json')
    for relative, expected in ref['frozen_core_lf_sha256'].items():
        if sha_lf(repository/relative) != expected:
            raise ValueError('Frozen contract/evaluator/helper changed: ' + relative)
    for relative, expected in ref['baseline_lf_sha256'].items():
        if sha_lf(repository/relative) != expected:
            raise ValueError('Frozen OCR/retrieval baseline/control changed: ' + relative)
    identity = ref['contract']
    actual = {'schema_canonical_sha256':digest(SCHEMA),
              'schema_wire_sha256':hashlib.sha256(wire(SCHEMA)).hexdigest(),
              'instruction_sha256':hashlib.sha256(INSTRUCTION.encode()).hexdigest(),
              'cases_sha256':digest(cases()), 'case_version':CASE_VERSION,'contract_version':CONTRACT_VERSION}
    if any(identity[k] != v for k,v in actual.items()):
        raise ValueError('Frozen contract/prompt/case identity drift')
    if sha_lf(repository/'docs/ANSWER_CONTRACT_QUALIFICATION_PLAN.md') != ref['plan_lf_sha256']:
        raise ValueError('Qualification plan/rubric changed')
    grammar = repository/'tests/fixtures/answer_contract_v3/schema.gbnf'
    if sha(grammar) != identity['grammar_sha256']:
        raise ValueError('Frozen effective grammar changed')
    return ref


def implementation(repository: Path) -> dict:
    files = [*sorted((repository/'src/finocr_answer').glob('*.py')),
             *sorted((repository/'src/finocr_qualification').glob('*.py')),
             *sorted((repository/'scripts').glob('*qualification*.py')),
             *sorted((repository/'scripts').glob('*answer*.py')),
             *sorted((repository/'tests').glob('test_qualification*.py')),
             repository/'tools/qualification_schema_probe.cpp',
             *sorted((repository/'docs').glob('*QUALIFICATION*')),
             repository/'docs/ANSWER_SETUP_LOCK.json',
             repository/'requirements/answer-windows-py312.lock.txt']
    values = {p.relative_to(repository).as_posix():sha(p) for p in files if p.is_file()}
    return {'files':values,'fingerprint':digest(values),
            'head':subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],text=True).strip(),
            'dirty_status':subprocess.check_output(['git','-C',str(repository),'status','--porcelain','--untracked-files=all'],text=True)}


def verify_existing_setup(path: Path, ref: dict) -> dict:
    if sha(path) != ref['historical_v2_setup_sha256']:
        raise ValueError('Historical v2 setup file changed')
    setup = read_json(path)
    require_lineage(setup)
    for key in ['backend_files','official_files','execution']:
        if setup[key] != ref[key]:
            raise ValueError('Historical asset/execution identity changed: ' + key)
    for key in ['model','server']:
        asset = setup[key]
        if any(asset[k] != v for k,v in ref[key].items()) or sha(Path(asset['path'])) != asset['sha256']:
            raise ValueError('Existing ' + key + ' bytes changed')
    if setup['runtime'] != runtime() or setup['runtime'] != ref['runtime']:
        raise ValueError('Existing Windows/Python/package runtime changed')
    if setup['runtime']['platform'] != 'Windows-11-10.0.22000-SP0':
        raise ValueError('Qualification is fixed to the reviewed Windows machine')
    assets = Path(setup['asset_root'])
    verify_assets(setup['lock'],assets)
    if tree(assets/'backend') != ref['backend_files'] or tree(assets/'official') != ref['official_files']:
        raise ValueError('Backend/official asset tree mismatch')
    return setup


def historical_paths(setup: dict) -> list[Path]:
    old = setup['lineage']
    v2 = Path(setup['campaign_root'])
    return [Path(old['setup_path']),Path(old['campaign_path']),Path(old['run_path']),
            v2/'setup_manifest.json',v2/'synthetic_campaign.json',v2/'run']


def verify_histories(setup: dict) -> dict:
    require_lineage(setup)
    old = read_json(Path(setup['lineage']['campaign_path']))
    ledger = read_json(Path(setup['campaign_root'])/'synthetic_campaign.json')
    for value in [old,ledger]:
        if value['attempted'] != 6 or len(value['requests']) != 6 or len(set(value['requests'])) != 6:
            raise ValueError('Both historical campaigns must remain exhausted at six')
    run = read_json(Path(setup['campaign_root'])/'run/run_manifest.json')
    if [r['request_sha256'] for r in run['records']] != ledger['requests'] or sum(r['checks']['mechanical_pass'] for r in run['records']) != 1:
        raise ValueError('Historical v2 result/ledger changed')
    return {'requests_spent':12,'remaining_authorized':0,'v2_mechanical_pass':'1/6'}


def verify_frozen_histories(setup: dict, ref: dict):
    paths=historical_paths(setup)
    for path,key in zip(paths,['v1_setup','v1_ledger','v1_run','v2_setup','v2_ledger','v2_run']):
        actual=snapshot([path])[str(path.resolve())]['files'] if path.is_dir() else sha(path)
        if actual!=ref['historical'][key]:
            raise ValueError('Historical file/tree drift: '+key)


def mandatory_paths(repository,setup,review,native_build):
    return [*historical_paths(setup),repository/'src/finocr',
        repository/'docs/EXPANSION_V1_CONTROL.json',repository/'docs/SYNTHETIC_V2_REVIEW.md',
        repository/'docs/SYNTHETIC_V2_RESULTS.json',review,native_build,Path(read_json(native_build)['executable'])]


def validate_review(directory: Path, ref: dict) -> dict:
    review = read_json(directory/'offline_conformance.json')
    if (review['status'] != 'offline_checks_pass' or review['inference_executed'] != 0 or
        review['additional_inference_authorized'] != 0 or not review['protected_artifacts_unchanged'] or
        not review['baseline_source_and_control_unchanged'] or review['tokenizer_check']['cases'] != ref['prompts'] or
        not review['tokenizer_check']['historical_token_parity_checked']):
        raise ValueError('The complete preserved offline gate is required')
    if any(review.get(k) != v for k,v in ref['contract'].items()):
        raise ValueError('Review is for another contract/case/grammar')
    if sha(directory/'schema-wire.json') != ref['contract']['schema_wire_sha256'] or sha(directory/'schema.gbnf') != ref['contract']['grammar_sha256']:
        raise ValueError('Review wire/grammar artifact changed')
    return review


def planned_cases(repository, assets, historical_run, ref):
    tokenizer, tokenizer_identity = load_local_tokenizer(repository,assets/'official',historical_run=historical_run)
    # Enforce exact historical parity anew, in addition to all six revised controls.
    from finocr_answer.conformance import tokenizer_checks
    observed = tokenizer_checks(tokenizer,historical_run=historical_run)
    if observed['cases'] != ref['prompts']:
        raise ValueError('Revised prompt/token/budget identity mismatch')
    planned = []
    for case in cases():
        turns, packed = pack(case,tokenizer)
        pages = {str(p['page_id']):tokenizer.decode(p['retained_token_ids'],skip_special_tokens=False,
                  clean_up_tokenization_spaces=False) for p in packed['retained']}
        planned.append({'case_id':case['task_id'].split(':')[1], 'turns':turns,'packing':packed,
                        'pages':pages,'source_pages_sha256':digest(case['pages']),
                        'question_sha256':hashlib.sha256(case['question'].encode()).hexdigest()})
    return planned, tokenizer_identity


def prepare_offline(repository: Path, v2_setup: Path, review: Path, source: Path,
                    native_build: Path, output: Path, *, preserve=(),
                    original_preservation_set=None, preservation_closeout=None) -> dict:
    repository, v2_setup, review, source, native_build, output = (
        p.resolve() for p in [repository,v2_setup,review,source,native_build,output])
    ref = frozen_reference(repository)
    # Read-only until paths are checked. This report never claims a campaign.
    setup = read_json(v2_setup)
    campaign_root = Path(setup['asset_root']).parent/'followups'/CAMPAIGN
    mandatory = mandatory_paths(repository,setup,review,native_build)
    extension,closeout_identity=[],None
    if original_preservation_set is not None or preservation_closeout is not None:
        if original_preservation_set is None or preservation_closeout is None:
            raise ValueError('Provide both original preservation set and final closeout')
        extension,closeout_identity=preservation_extension(original_preservation_set,preservation_closeout)
    protected = list(dict.fromkeys([*mandatory,*extension,*[Path(p).resolve() for p in preserve]]))
    for root in [repository,source,Path(setup['asset_root']),campaign_root,*protected]:
        root = root.resolve()
        if output == root or root in output.parents or output in root.parents:
            raise ValueError('Offline output must not overlap code/assets/history/campaign/protected paths')
    if output.exists() or campaign_root.exists():
        raise FileExistsError('Preserve existing review/campaign; no restart')
    before = snapshot(protected)
    output.mkdir(parents=True)
    report = {'kind':'qualification_offline_preparation_not_authorization', 'version':VERSION,
        'status':'checking','inference_executed':0,'additional_inference_authorized':0,
        'remaining_authorized_requests':0,'execution_enabled':False,'benchmark_generation_enabled':False,
        'protected':before,'repository':str(repository),'v2_setup':str(v2_setup),
        'campaign_root':str(campaign_root),'source':str(source),'native_build':str(native_build),
        'contract_review':str(review),'preservation_closeout':closeout_identity}
    started=time.monotonic()
    try:
        verify_existing_setup(v2_setup,ref)
        report['historical'] = verify_histories(setup)
        verify_frozen_histories(setup,ref)
        validate_review(review,ref)
        report['runtime'] = runtime()
        report['implementation'] = implementation(repository)
        report['frozen_reference'] = ref
        report['resources'] = preflight_resources(output)
        write_bytes(output/'schema-wire.json',wire(SCHEMA))
        grammar = (repository/'tests/fixtures/answer_contract_v3/schema.gbnf').read_bytes()
        report['native_grammar'] = compare_native(repository,source,read_json(native_build),output/'schema-wire.json',grammar)
        packing_start=time.monotonic()
        report['planned'], report['tokenizer'] = planned_cases(repository,Path(setup['asset_root']),
            Path(setup['campaign_root'])/'run',ref)
        report['local_packing_checks_wall_seconds']=time.monotonic()-packing_start
        report['status'] = 'offline_ready_for_separate_review_not_authorization'
    except Exception as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        report['offline_preflight_wall_seconds']=time.monotonic()-started
        try:
            report['preserved_after'] = assert_preserved(before)
            report['preservation_pass'] = True
        except Exception as exc:
            report.update(status='failed_preservation',preservation_pass=False,preservation_error=str(exc))
        write_json(output/'offline_preparation.json',report)
    return report
