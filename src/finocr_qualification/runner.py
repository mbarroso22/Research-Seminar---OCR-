"""V3-only lifecycle requiring separately reviewed, exact external approval."""
from __future__ import annotations
import hashlib
from pathlib import Path
import time

from finocr_answer.contract import SCHEMA, digest, strict_json, wire, validate_schema
from finocr_answer.feasibility import parse_stream
from finocr_answer.grammar import Grammar
from finocr_answer.pause import require_inference_authorized
from finocr_answer.validation import functional_checks, validate_response
from .backend import WindowsBackend
from .evidence import CASES, Journal, assert_preserved, export_evidence, write_bytes, write_json, sync_directory
from .preparation import (CAMPAIGN, VERSION, frozen_reference, implementation, read_json,
    verify_existing_setup, verify_histories, verify_frozen_histories, planned_cases, mandatory_paths)
from .probe import pinned_source
from .resources import preflight_resources
from .preservation import preservation_extension
from finocr_answer.setup import sha, runtime
from .authorization import (VerifiedAuthorization, verify_authorization, revalidate_authorization,
    guard_authorization_window, AuthorizationRejected)


def request_payload(tokens):
    return {'prompt':tokens,'n_predict':1024,'temperature':0,'seed':0,'top_k':1,'top_p':1.0,
            'min_p':0.0,'repeat_penalty':1.0,'presence_penalty':0.0,'frequency_penalty':0.0,
            'cache_prompt':False,'json_schema':SCHEMA,'stream':True,'id_slot':0}


def validate_preparation(report: dict, repository: Path):
    if (report['kind']!='qualification_offline_preparation_not_authorization' or
        report['version']!=VERSION or report['status']!='offline_ready_for_separate_review_not_authorization' or
        report['additional_inference_authorized']!=0 or report['remaining_authorized_requests']!=0 or
        report['inference_executed']!=0 or report['execution_enabled'] is not False):
        raise ValueError('Require a passing offline report; it is not authorization')
    ref=frozen_reference(repository)
    if report['frozen_reference']!=ref or report['implementation']!=implementation(repository):
        raise ValueError('Frozen reference/code/HEAD/dirty inventory changed since review')
    if report['runtime']!=runtime():raise ValueError('Runtime changed since offline review')
    setup=verify_existing_setup(Path(report['v2_setup']),ref)
    verify_histories(setup)
    verify_frozen_histories(setup,ref)
    required=mandatory_paths(repository,setup,Path(report['contract_review']),Path(report['native_build']))
    if report.get('preservation_closeout') is not None:
        identity=report['preservation_closeout']
        extension,current_identity=preservation_extension(Path(identity['original_preservation_set']),
            Path(identity['closeout_directory']))
        if current_identity!=identity:raise ValueError('Final preservation closeout binding changed')
        required.extend(extension)
    if any(str(p.resolve()) not in report['protected'] for p in required):
        raise ValueError('Mandatory preservation roots removed from offline report')
    pinned_source(Path(report['source']))
    assert_preserved(report['protected'])
    planned,_=planned_cases(repository,Path(setup['asset_root']),Path(setup['campaign_root'])/'run',ref)
    if report['planned']!=planned:raise ValueError('Frozen planned input/evaluation excerpts changed')
    if [p['case_id'] for p in planned]!=list(CASES):raise ValueError('Exactly six fictional cases required')
    expected=Path(setup['asset_root']).parent/'followups'/CAMPAIGN
    if Path(report['campaign_root']).resolve()!=expected.resolve():raise ValueError('No alternate campaign/output location')
    preflight_resources(expected.parent)
    return setup,planned


def _engine(report: dict, repository: Path, authorization: VerifiedAuthorization, *, factory=WindowsBackend) -> dict:
    """Internal lifecycle tested only with mocked transports and temporary fixtures.

    No ticket issuer. Absent separately installed operator approval, public run()
    still reaches the unchanged pause. Tests use temporary fixtures and mocks.
    """
    authorization=revalidate_authorization(authorization,report,repository)
    protected=dict(report['protected'])
    for path,value in authorization.protected.items():
        if path in protected and protected[path]!=value:
            raise AuthorizationRejected('Conflicting preservation binding for approval evidence')
        protected[path]=value
    # Trust the root only after checking the immutable historical setup hash.
    ref=frozen_reference(repository)
    setup_path=Path(report['v2_setup'])
    if sha(setup_path)!=ref['historical_v2_setup_sha256']:raise ValueError('Wrong historical setup')
    setup=read_json(setup_path)
    root=Path(setup['asset_root']).parent/'followups'/CAMPAIGN
    if Path(report['campaign_root']).resolve()!=root.resolve():raise ValueError('No alternate campaign anchor')
    journal=Journal(root,{'authorization':authorization.identity,
        'offline_report_sha256':digest(report),'runner_version':VERSION})
    output=root/'run';output.mkdir();sync_directory(root)
    result={'kind':'synthetic_development_qualification','version':VERSION,'status':'preflight',
        'historical_requests_spent':12,'attempted':0,'submission_attempts':0,'responses_received':0,'valid_contract_outputs':0,
        'records':[],'unattempted':list(CASES),'benchmark_generation_enabled':False,
        'qualification_pass':False,'manual_review':'pending_two_independent_reviewers_and_adjudication',
        'authorization':authorization.identity,'input_changed_case':'capacity'}
    backend=None;current=None;started=time.monotonic()
    try:
        write_json(output/'offline_preparation.json',report)
        approval_output=output/'authorization';approval_output.mkdir();sync_directory(output)
        write_bytes(approval_output/'operator-approval.original.json',authorization.approval_bytes)
        write_bytes(approval_output/'authorization.original.json',authorization.authorization_bytes)
        write_bytes(approval_output/'offline-preparation.original.json',authorization.preparation_bytes)
        write_json(approval_output/'verified-binding.json',authorization.identity)
        write_bytes(output/'plan-and-evaluator-rubric.md',(repository/'docs/ANSWER_CONTRACT_QUALIFICATION_PLAN.md').read_bytes())
        write_json(output/'frozen-identities.json',ref)
        write_json(output/'preservation-before.json',protected)
        validation_start=time.monotonic()
        setup,planned=validate_preparation(report,repository)
        result['validation_and_repacking_wall_seconds']=time.monotonic()-validation_start
        grammar=Grammar((repository/'tests/fixtures/answer_contract_v3/schema.gbnf').read_text(encoding='utf-8'))
        guard_authorization_window(authorization)
        backend=factory(setup,output,root)
        backend.start()
        # All six backend controls must pass BEFORE any completion is charged.
        controls_start=time.monotonic()
        for item in planned:
            rendered=backend.metadata('/apply-template',{'messages':item['turns']})['prompt']
            tokens=backend.metadata('/tokenize',{'content':rendered,'add_special':False,'parse_special':True})['tokens']
            if rendered!=item['packing']['prompt'] or tokens!=item['packing']['token_ids']:
                raise ValueError('Backend/local prompt or token parity mismatch')
        result['all_six_backend_controls_wall_seconds']=time.monotonic()-controls_start
        write_json(output/'all-six-backend-controls.json',{'verified':True,'completion_attempts':0,
            'wall_seconds':result['all_six_backend_controls_wall_seconds']})
        for item in planned:
            case=item['case_id'];current=None
            assert_preserved(protected);backend.guard()
            directory=output/case;directory.mkdir();sync_directory(output)
            packed=item['packing'];payload=request_payload(packed['token_ids'])
            encoded=wire(payload);request_hash=hashlib.sha256(encoded).hexdigest()
            write_bytes(directory/'request.json',encoded)
            write_bytes(directory/'prompt.txt',packed['prompt'].encode())
            write_json(directory/'packing.json',packed)
            write_json(directory/'included-pages.json',item['pages'])
            write_json(directory/'source-identities.json',{'source_pages_sha256':item['source_pages_sha256'],
                'question_sha256':item['question_sha256'],'canonical_payload_sha256':digest(payload),
                'ordered_wire_sha256':request_hash})
            before=backend.bracket()
            guard_authorization_window(authorization)
            # No filesystem/backend operation between successful durable charge and submission.
            journal.charge(case,request_hash)
            current={'case_id':case,'status':'attempt_started','request_wire_sha256':request_hash,
                     'started_ns':time.time_ns()}
            result['records'].append(current);result['attempted']=journal.attempted
            result['submission_attempts']+=1
            transport=backend.complete(payload,directory)
            if isinstance(transport,dict):current['transport']=transport
            after=backend.bracket()
            current['resource_brackets']={'before':before,'after':after}
            current['transport_received']=True;result['responses_received']+=1
            raw=(directory/'raw-response.sse').read_bytes()
            content,final=parse_stream(raw)
            write_bytes(directory/'raw-content.txt',content.encode())
            write_json(directory/'backend-final.json',final)
            predicted=final.get('tokens_predicted')
            if (type(predicted) is not int or not 0<predicted<=1024 or final.get('stop_type')=='limit' or
                final.get('truncated') or not content.strip()):
                raise ValueError('Invalid/empty/limited/truncated completion; terminal stop')
            if final.get('tokens_evaluated',len(payload['prompt']))!=len(payload['prompt']):
                raise ValueError('Backend evaluated another input-token count')
            current.update(generated_tokens=predicted,backend_timings=final.get('timings'))
            # Invalid JSON/schema/grammar is terminal. Generic mechanical errors are retained.
            value=strict_json(content);validate_schema(value)
            if not grammar.accepts(content):raise ValueError('Output outside the frozen ordered effective grammar')
            result['valid_contract_outputs']+=1
            write_json(directory/'parsed.json',value)
            pages={int(p):text for p,text in item['pages'].items()}
            generic=validate_response(value,pages);checks=functional_checks(value,case,pages)
            write_json(directory/'generic-mechanics.json',generic)
            write_json(directory/'case-checks.json',checks)
            current.update(status='mechanical_pass_manual_pending' if checks['mechanical_pass'] else 'mechanical_failed',
                mechanical_pass=checks['mechanical_pass'],axes={
                    'contract':{'strict_json':True,'schema':True,'grammar':True,
                        'invariant_issues':[i for i in generic['issues'] if i['code'] in {
                            'abstention_conflict','missing_abstention_facts','unit_scale_dimension',
                            'undefined_operand','operand_expression_mismatch','unlinked_calculation','calculation_result_quantity'}]},
                    'numerical':{'applicable':case not in {'missing','capacity'},
                                 'required_component_checks':{k:v for k,v in checks.items() if k.startswith('quantity_')},
                                 'independent_arithmetic':checks.get('calculation'),
                                 'manual_formula_and_final_answer':'pending' if case not in {'missing','capacity'} else 'N/A'},
                    'source_support':{'literal_checks_pass':checks['citation_structure'],'semantic_review':'pending'},
                    'interpretation':'pending','resource_feasibility':'request_brackets_pass'})
            journal.finish(case,current)
            current=None
        backend.guard()
        result['status']='completed_manual_review_pending'
    except BaseException as exc:
        result.update(status='terminal_stop',error=f'{type(exc).__name__}: {exc}')
        if current is not None:
            current.update(status='terminal_failure',error=result['error'])
            try:journal.finish(current['case_id'],current)
            except Exception as record_error:result['journal_finish_error']=str(record_error)
    finally:
        if backend is not None:
            try:backend.close()
            except Exception as exc:result.update(status='terminal_stop',cleanup_error=str(exc))
            result['resources']=backend.summary()
            if not result['resources'].get('sample_count') or result['resources'].get('measurement_errors'):
                result.update(status='terminal_stop',resource_failure=True)
        result['attempted']=journal.attempted
        result['unattempted']=list(CASES[journal.attempted:])
        result['cumulative_charged_attempts']=12+journal.attempted
        result['wall_seconds']=time.monotonic()-started
        try:
            result['preservation_after']=assert_preserved(protected)
            # Rehash model/backend/official assets and runtime after stopping owned process.
            verify_existing_setup(Path(report['v2_setup']),ref)
            result['preservation_pass']=True
        except Exception as exc:
            result.update(status='terminal_stop',preservation_pass=False,preservation_error=str(exc))
        result['automated_checks_pass']=bool(result['status']=='completed_manual_review_pending' and
            journal.attempted==6 and all(r.get('mechanical_pass') for r in result['records']) and result['preservation_pass'])
        if result['status']=='completed_manual_review_pending' and not result['automated_checks_pass']:
            result['status']='completed_mechanical_failures_manual_review_pending'
        try:journal.close(result['status'])
        except Exception as exc:result.update(status='terminal_stop',journal_close_error=str(exc),automated_checks_pass=False)
        write_json(output/'run_manifest.json',result)
        write_json(output/'manual-review-template.json',{'kind':'human_evaluation_only','minimum_independent_reviewers':2,
            'qualification_pass':False,'records':[{'case_id':c,'reviewer_id':None,'date':None,
            'contract':None,'numerical':None if c not in {'missing','capacity'} else 'N/A',
            'source_support':None,'interpretation':None,'evidence_and_recomputation':None} for c in CASES],
            'adjudication':'pending; retain both independent ratings; no inference to resolve disagreements'})
        try:
            if result.get('cleanup_error'):raise ValueError('Cleanup failed; defer export until writers are quiescent')
            result['export']=export_evidence(root,root.with_name(root.name+'-evidence.zip'))
        except Exception as exc:
            write_json(root/'export-failure.json',{'error':str(exc),'retry_inference_permitted':False})
            result['export_error']=str(exc)
    return result


def run(preparation: Path, repository: Path, authorization: Path | None = None) -> dict:
    if authorization is None:
        require_inference_authorized()  # First operation on the default, genuinely paused path.
    verified=verify_authorization(preparation,repository,authorization)
    return _engine(verified.report,repository,verified)
