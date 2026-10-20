"""All lifecycle calls use temporary fixture ledgers and mocked transports only."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import ExitStack

from finocr_answer.contract import SCHEMA, canonical, wire
from finocr_answer.conformance_fixtures import positives, pages
from finocr_answer.pause import InferencePausedError
from finocr_qualification.evidence import (CASES, Journal, assert_preserved,
    inspect_journal, snapshot, write_bytes, write_json, export_evidence)
from finocr_qualification.preparation import (CAMPAIGN, frozen_reference, implementation,
    validate_review, verify_frozen_histories, verify_existing_setup, prepare_offline)
from finocr_qualification.resources import device_reading, check_sample, preflight_resources, ResourceMonitor, GIB
from finocr_qualification.backend import runtime_log, WindowsBackend
from finocr_qualification.runner import run, _engine, request_payload, validate_preparation
from finocr_qualification.authorization import VerifiedAuthorization

REPO=Path(__file__).resolve().parents[1]


class FakeBackend:
    def __init__(self,setup,output,root):
        self.output,self.root=output,root
        self.calls=[];self.closed=False;self.responses=positives()
        self.fail=None;self.mismatch=False;self.change=None
    def start(self):
        write_json(self.output/'launch.json',{'mock_transport_only':True})
        write_json(self.output/'runtime_observed.json',{'mock_transport_only':True})
        if self.fail=='startup':raise ValueError('mock startup failure')
    def guard(self):
        if self.fail=='guard':raise ValueError('mock runtime transition')
    def metadata(self,route,payload):
        if route=='/apply-template':return {'prompt':payload['messages'][0]['content']}
        return {'tokens':[-1] if self.mismatch else [CASES.index(payload['content'].split(':')[1])+1]}
    def bracket(self):
        if self.fail=='resource':raise ValueError('mock resource threshold')
        if self.fail=='post_resource' and self.calls:raise ValueError('mock post-request threshold')
        return {'mock_only':True,'time_ns':1}
    def complete(self,payload,directory):
        case=directory.name
        # Test durable charge before the mocked submission. No real endpoint exists.
        evidence=inspect_journal(self.root)
        if evidence['attempted']!=len(self.calls)+1:raise AssertionError('Not durably charged')
        self.calls.append(copy.deepcopy(payload))
        content=wire(self.responses[case]).decode() if not isinstance(self.responses[case],str) else self.responses[case]
        if self.fail in {'transport','deadline','cancel'}:
            write_bytes(directory/'raw-response.sse',b'data: partial-mock-fixture\n')
            if self.fail=='cancel':raise KeyboardInterrupt('mock cancellation')
            if self.fail=='deadline':raise TimeoutError('mock total wall deadline')
            raise OSError('mock transport failure')
        if self.change:self.change()
        final={'stop':True,'content':content,'tokens_predicted':1025 if self.fail=='tokens' else 100,
               'stop_type':'limit' if self.fail=='limit' else 'eos',
               'truncated':self.fail=='truncated','timings':{'mock_only':True}}
        write_bytes(directory/'raw-response.sse',b'data: '+wire(final)+b'\n\n')
        write_json(directory/'transport.json',{'status':'received','mock_only':True})
    def close(self):self.closed=True
    def summary(self):return {'sample_count':20,'measurement_errors':['mock sample failure'] if self.fail=='monitor' else []}


class EngineFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        assets=self.base/'assets';assets.mkdir();(self.base/'followups').mkdir()
        self.setup={'asset_root':str(assets)}
        self.setupfile=self.base/'historical-setup.json';write_json(self.setupfile,self.setup)
        from finocr_answer.setup import sha
        self.ref={'historical_v2_setup_sha256':sha(self.setupfile)}
        old=self.base/'old';old.mkdir();(old/'ledger').write_bytes(b'EXHAUSTED MOCK HISTORY')
        self.old=old
        self.root=self.base/'followups'/CAMPAIGN
        self.report={'v2_setup':str(self.setupfile),'campaign_root':str(self.root),'protected':snapshot([old])}
        self.planned=[{'case_id':name,'turns':[{'role':'system','content':'MOCK:'+name}],
            'packing':{'prompt':'MOCK:'+name,'token_ids':[i+1]},
            'pages':{str(k):v for k,v in pages(name).items()},
            'source_pages_sha256':'mock-page-identity','question_sha256':'mock-question-identity'} for i,name in enumerate(CASES)]
        self.stack=ExitStack()
        self.stack.enter_context(patch('finocr_qualification.runner.frozen_reference',return_value=self.ref))
        self.stack.enter_context(patch('finocr_qualification.runner.validate_preparation',return_value=(self.setup,self.planned)))
        self.stack.enter_context(patch('finocr_qualification.runner.verify_existing_setup',return_value=self.setup))
        # These are temporary mock bindings, never real operator approvals.
        self.auth=VerifiedAuthorization(self.base/'mock-preparation',self.base/'mock-approval',
            self.base/'mock-authorization',canonical(self.report),b'{}',canonical({
                'authorization_id':'MOCK-ONLY-NOT-AUTHORIZATION','approval_reference':'mock transport test',
                'bindings':{},'limits':{'mock_only':True}}))
        for path,data in [(self.auth.preparation_path,self.auth.preparation_bytes),
                (self.auth.approval_path,self.auth.approval_bytes),(self.auth.authorization_path,self.auth.authorization_bytes)]:
            write_bytes(path,data)
        self.stack.enter_context(patch('finocr_qualification.runner.revalidate_authorization',
            side_effect=lambda a,*args: a if isinstance(a,VerifiedAuthorization) else
                (_ for _ in ()).throw(ValueError('No mock binding supplied'))))
        self.stack.enter_context(patch('finocr_qualification.runner.guard_authorization_window'))
        self.backend=None
        self.configure=lambda b:None
    def tearDown(self):self.stack.close();self.temp.cleanup()
    def factory(self,*args):
        self.backend=FakeBackend(*args);self.configure(self.backend);return self.backend
    def execute(self):return _engine(self.report,REPO,self.auth,factory=self.factory)
    def test_mock_success_retains_six_charges_and_never_promotes_manual_support(self):
        result=self.execute()
        self.assertEqual(len(self.backend.calls),6);self.assertTrue(result['automated_checks_pass'])
        self.assertFalse(result['qualification_pass']);self.assertEqual(result['cumulative_charged_attempts'],18)
        self.assertEqual(result['submission_attempts'],6)
        self.assertIn('all_six_backend_controls_wall_seconds',result)
        self.assertEqual(result['unattempted'],[]);self.assertTrue(self.backend.closed)
        journal=inspect_journal(self.root)
        self.assertEqual(journal['attempted'],6);self.assertTrue(journal['terminal_recorded']);self.assertFalse(journal['restart_permitted'])
        for case in CASES:
            self.assertTrue((self.root/'run'/case/'raw-response.sse').exists())
            self.assertTrue((self.root/'run'/case/'generic-mechanics.json').exists())
        self.assertTrue(result['export']['verified'])
    def test_all_six_backend_controls_are_verified_before_first_charge(self):
        self.configure=lambda b:setattr(b,'mismatch',True)
        result=self.execute()
        self.assertEqual(result['attempted'],0);self.assertEqual(self.backend.calls,[])
        self.assertEqual(result['unattempted'],list(CASES));self.assertEqual(result['status'],'terminal_stop')
    def test_existing_anchor_cannot_restart_even_with_a_new_output_name(self):
        self.execute()
        with self.assertRaises(FileExistsError):self.execute()
        self.report['campaign_root']=str(self.base/'different')
        with self.assertRaises(ValueError):self.execute()
    def test_no_authorization_binding_means_no_anchor(self):
        with self.assertRaises(ValueError):_engine(self.report,REPO,'',factory=self.factory)
        self.assertFalse(self.root.exists())
    def test_schema_valid_wrong_sign_is_retained_without_retry_and_sequence_continues(self):
        def change(b):b.responses['signed']['quantities'][0]['value']='12.5'
        self.configure=change;result=self.execute()
        self.assertEqual(len(self.backend.calls),6);self.assertFalse(result['automated_checks_pass'])
        self.assertEqual(result['records'][0]['status'],'mechanical_failed')
    def test_undefined_operand_remains_failure_and_does_not_change_request(self):
        def change(b):b.responses['scale']['calculation']['operand_ids'].append('scale_factor')
        self.configure=change;result=self.execute()
        self.assertEqual(len(self.backend.calls),6);self.assertFalse(result['records'][1]['mechanical_pass'])
    def test_invalid_json_schema_and_reordered_grammar_each_stop_without_retry(self):
        for value in ['{invalid','{}',canonical(positives()['signed']).decode()]:
            with self.subTest(value=value[:30]):
                # Each subcase uses a wholly separate temporary test fixture.
                if self.root.exists():
                    import shutil
                    shutil.rmtree(self.root)
                    for p in self.base.glob(CAMPAIGN+'-evidence.zip*'):p.unlink()
                self.configure=lambda b:setattr(b,'responses',{**b.responses,'signed':value})
                result=self.execute()
                self.assertEqual(result['attempted'],1);self.assertEqual(len(self.backend.calls),1)
                self.assertEqual(result['status'],'terminal_stop')
                self.assertTrue((self.root/'run/signed/raw-content.txt').exists())
    def test_transport_deadline_and_cancellation_keep_partial_bytes_and_spend_attempt(self):
        for failure in ['transport','deadline','cancel']:
            with self.subTest(failure=failure):
                if self.root.exists():
                    import shutil
                    shutil.rmtree(self.root)
                    for p in self.base.glob(CAMPAIGN+'-evidence.zip*'):p.unlink()
                self.configure=lambda b:setattr(b,'fail',failure)
                result=self.execute()
                self.assertEqual(result['attempted'],1);self.assertEqual(len(self.backend.calls),1)
                self.assertEqual(result['status'],'terminal_stop');self.assertTrue(self.backend.closed)
                self.assertIn(b'partial-mock-fixture',(self.root/'run/signed/raw-response.sse').read_bytes())
    def test_output_limit_truncation_and_invalid_token_counts_are_terminal(self):
        for failure in ['tokens','limit','truncated']:
            with self.subTest(failure=failure):
                if self.root.exists():
                    import shutil
                    shutil.rmtree(self.root)
                    for p in self.base.glob(CAMPAIGN+'-evidence.zip*'):p.unlink()
                self.configure=lambda b:setattr(b,'fail',failure)
                result=self.execute();self.assertEqual(result['attempted'],1);self.assertFalse(result['automated_checks_pass'])
    def test_startup_runtime_and_pre_request_resource_failure_spend_zero(self):
        for failure in ['startup','guard','resource']:
            with self.subTest(failure=failure):
                if self.root.exists():
                    import shutil
                    shutil.rmtree(self.root)
                    for p in self.base.glob(CAMPAIGN+'-evidence.zip*'):p.unlink()
                self.configure=lambda b:setattr(b,'fail',failure)
                result=self.execute();self.assertEqual(result['attempted'],0);self.assertTrue(self.backend.closed)
    def test_post_request_resource_failure_stops_after_one_charge(self):
        self.configure=lambda b:setattr(b,'fail','post_resource')
        result=self.execute();self.assertEqual(result['attempted'],1);self.assertEqual(result['status'],'terminal_stop')
    def test_monitor_failure_cannot_become_resource_or_overall_success(self):
        self.configure=lambda b:setattr(b,'fail','monitor')
        result=self.execute();self.assertFalse(result['automated_checks_pass']);self.assertEqual(result['status'],'terminal_stop')
    def test_added_historical_file_is_detected_before_another_submission(self):
        self.configure=lambda b:setattr(b,'change',lambda:(self.old/'unexpected').write_bytes(b'mock drift'))
        result=self.execute();self.assertEqual(result['attempted'],1);self.assertFalse(result['preservation_pass'])
    def test_approval_source_mutation_stops_after_current_mock_attempt(self):
        self.configure=lambda b:setattr(b,'change',lambda:self.auth.approval_path.write_bytes(b'MOCK DRIFT'))
        result=self.execute();self.assertEqual(result['attempted'],1);self.assertFalse(result['preservation_pass'])
        self.assertEqual(len(self.backend.calls),1);self.assertEqual(result['status'],'terminal_stop')
    def test_expiry_during_preflight_or_between_submissions_is_terminal_without_retry(self):
        with patch('finocr_qualification.runner.guard_authorization_window',
                   side_effect=[None,None,ValueError('MOCK EXPIRED')]):result=self.execute()
        self.assertEqual(result['attempted'],1);self.assertEqual(len(self.backend.calls),1)
        self.assertEqual(result['status'],'terminal_stop');self.assertEqual(len(result['unattempted']),5)
    def test_changed_code_or_history_in_preflight_claims_zero_attempt_terminal_campaign(self):
        with patch('finocr_qualification.runner.validate_preparation',side_effect=ValueError('mock code drift')):
            result=self.execute()
        self.assertEqual(result['attempted'],0);self.assertIsNone(self.backend)
        self.assertTrue(inspect_journal(self.root)['terminal_recorded'])
    def test_terminal_event_write_failure_cannot_leave_automated_success(self):
        with patch.object(Journal,'close',side_effect=OSError('mock final fsync failure')):
            result=self.execute()
        self.assertFalse(result['automated_checks_pass']);self.assertEqual(result['status'],'terminal_stop')
    def test_fsync_failure_blocks_transport_and_cannot_be_retried(self):
        original=Journal.charge
        def fail(journal,*args):
            with patch('finocr_qualification.evidence.os.fsync',side_effect=OSError('mock disk failure')):
                return original(journal,*args)
        with patch.object(Journal,'charge',fail):result=self.execute()
        self.assertEqual(self.backend.calls,[]);self.assertEqual(result['attempted'],1)
        self.assertEqual(result['submission_attempts'],0)
        self.assertFalse(result['automated_checks_pass']);self.assertFalse(inspect_journal(self.root)['restart_permitted'])
    def test_ordered_wire_contains_no_evaluator_labels_or_expected_status(self):
        self.execute()
        for payload in self.backend.calls:
            self.assertEqual(next(iter(payload['json_schema']['anyOf'][0]['properties'])),'status')
            self.assertEqual(set(payload),set(request_payload([])))
            self.assertNotIn('expected_status',wire(payload).decode())
            self.assertNotIn('financebench',wire(payload).decode().lower())


class AccountingAndExportTests(unittest.TestCase):
    def test_journal_enforces_pending_order_exhaustion_and_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'fixture';j=Journal(root,{'mock_only':True})
            with self.assertRaises(ValueError):j.charge('scale','x')
            for c in CASES:
                j.charge(c,'x')
                with self.assertRaises(ValueError):j.charge(c,'x')
                j.finish(c,{'mock_only':True})
                with self.assertRaises(ValueError):j.finish(c,{})
            with self.assertRaises(ValueError):j.charge('signed','x')
            j.close('mock terminal')
            with self.assertRaises(ValueError):j.charge('signed','x')
            with self.assertRaises(FileExistsError):Journal(root,{})
    def test_uncertain_attempt_is_spent_and_recovery_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'fixture';j=Journal(root,{});j.charge('signed','x')
            before=snapshot([root]);r=inspect_journal(root)
            self.assertEqual(r['uncertain_cases'],['signed']);self.assertFalse(r['restart_permitted'])
            self.assertEqual(before,snapshot([root]))
    def test_hash_chain_detects_ledger_edits_and_torn_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'fixture';j=Journal(root,{});j.charge('signed','x');j.finish('signed',{})
            p=root/'events/0001-attempt_started.json';p.write_text('{}')
            with self.assertRaises((ValueError,KeyError)):inspect_journal(root)
    def test_exclusive_evidence_and_deleted_or_added_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_bytes(root/'a',b'original');before=snapshot([root])
            with self.assertRaises(FileExistsError):write_bytes(root/'a',b'changed')
            (root/'b').write_bytes(b'extra')
            with self.assertRaises(ValueError):assert_preserved(before)
            (root/'b').unlink();(root/'a').unlink()
            with self.assertRaises(ValueError):assert_preserved(before)
    def test_export_verifies_all_files_and_refuses_overwrite_or_nested_archive(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'evidence';root.mkdir();(root/'raw').write_bytes(b'partial mock output')
            archive=Path(tmp)/'export.zip';r=export_evidence(root,archive)
            self.assertTrue(r['verified'])
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(z.read('raw'),b'partial mock output');self.assertIn('_EXPORT_MANIFEST.json',z.namelist())
            with self.assertRaises(ValueError):export_evidence(root,archive)
            with self.assertRaises(ValueError):export_evidence(root,root/'nested.zip')


class FrozenAndPauseTests(unittest.TestCase):
    def test_entire_frozen_contract_evaluator_and_plan_reference_match(self):
        ref=frozen_reference(REPO)
        self.assertEqual(len(ref['prompts']),6)
        self.assertEqual([p['input_tokens'] for p in ref['prompts']],[620,613,644,636,623,5120])
        self.assertEqual(ref['prompts'][-1]['body_tokens'],[800]*5)
    def test_new_runner_binding_is_separate_from_old_source_fingerprint(self):
        binding=implementation(REPO)
        self.assertIn('src/finocr_qualification/runner.py',binding['files'])
        self.assertIn('src/finocr_answer/validation.py',binding['files'])
        self.assertNotEqual(binding['fingerprint'],'d3abdda241189dd1af5781499f9f052cf9cb00e566dab80d30288b2ae7dd0587')
    def test_public_pause_precedes_reads_processes_and_claims_even_with_override_env(self):
        with patch.dict(os.environ,{'FINOCR_ALLOW_INFERENCE':'1','FINOCR_REQUEST_BUDGET':'6'}), \
             patch('finocr_qualification.runner.read_json',side_effect=AssertionError('No reads')), \
             patch('subprocess.Popen',side_effect=AssertionError('No process')), \
             patch('finocr_qualification.runner.Journal',side_effect=AssertionError('No ledger')):
            with self.assertRaises(InferencePausedError):run(Path('absent'),REPO)
    def test_cli_pause_creates_no_execution_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=subprocess.run([sys.executable,str(REPO/'scripts/run_qualification.py'),
                '--preparation',str(root/'absent')],capture_output=True,text=True,
                env={**os.environ,'PYTHONPATH':str(REPO/'src'),'PYTHONDONTWRITEBYTECODE':'1'})
            self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stdout)['status'],'inference_paused')
            self.assertEqual(list(root.iterdir()),[])
    def test_review_requires_complete_tokenizer_gate_and_exact_frozen_identities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_json(root/'offline_conformance.json',{'status':'grammar_and_fixture_checks_pass_tokenizer_pending'})
            with self.assertRaises(ValueError):validate_review(root,frozen_reference(REPO))
    def test_history_hashes_detect_even_a_consistent_rewritten_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'history';p.write_bytes(b'new six-request ledger')
            with patch('finocr_qualification.preparation.historical_paths',return_value=[p]):
                with self.assertRaises(ValueError):verify_frozen_histories({}, {'historical':{'v1_setup':'original hash'}})
    def test_frozen_reference_file_cannot_be_swapped_with_new_expectations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'docs').mkdir();(root/'docs/QUALIFICATION_FROZEN_IDENTITIES.json').write_text('{}')
            with self.assertRaises(ValueError):frozen_reference(root)


class OfflinePreparationTests(unittest.TestCase):
    def test_offline_preparation_roundtrip_and_binding_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);assets=root/'assets';assets.mkdir();(root/'followups').mkdir()
            setupfile=root/'v2.json';setup={'asset_root':str(assets),'campaign_root':str(root/'old-v2')}
            write_json(setupfile,setup);old=root/'old';old.write_bytes(b'mock historical evidence')
            build=root/'build.json';write_json(build,{'executable':str(old)})
            planned=[{'case_id':c,'mock_packing_only':True} for c in CASES]
            for module in ['finocr_qualification.preparation','finocr_qualification.runner']:
                for name,value in [('verify_existing_setup',setup),('verify_histories',{}),
                    ('verify_frozen_histories',None),('mandatory_paths',[old]),
                    ('runtime',{'mock_only':True}),('planned_cases',(planned,{})),('preflight_resources',{})]:
                    stack.enter_context(patch(module+'.'+name,return_value=value))
            stack.enter_context(patch('finocr_qualification.preparation.validate_review',return_value={}))
            stack.enter_context(patch('finocr_qualification.preparation.compare_native',return_value={'mock_only':True}))
            stack.enter_context(patch('finocr_qualification.runner.pinned_source'))
            # Contract/evaluator/fingerprint checks are real; only machine/assets/tokenizer are mocked.
            out=root/'offline'
            report=prepare_offline(REPO,setupfile,root/'old-review',root/'source',build,out)
            self.assertEqual(report['status'],'offline_ready_for_separate_review_not_authorization')
            self.assertEqual(validate_preparation(report,REPO)[1],planned)
            for field,value in [('protected',{}),('planned',[]),('remaining_authorized_requests',6),
                                ('implementation',{'fingerprint':'changed'})]:
                altered={**report,field:value}
                with self.assertRaises(ValueError):validate_preparation(altered,REPO)
            self.assertFalse((root/'followups'/CAMPAIGN).exists())
    def test_failed_offline_preparation_retains_report_and_creates_no_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);assets=root/'assets';assets.mkdir();(root/'followups').mkdir()
            setup=root/'v2.json';write_json(setup,{'asset_root':str(assets)})
            protect=root/'old';protect.write_bytes(b'mock original')
            build=root/'build.json';write_json(build,{'executable':str(protect)})
            review=root/'review';review.mkdir();source=root/'source';source.mkdir();out=root/'offline'
            with patch('finocr_qualification.preparation.frozen_reference',return_value={}), \
                 patch('finocr_qualification.preparation.mandatory_paths',return_value=[protect]), \
                 patch('finocr_qualification.preparation.verify_existing_setup',side_effect=ValueError('mock runtime drift')):
                report=prepare_offline(REPO,setup,review,source,build,out)
            self.assertEqual(report['status'],'failed');self.assertEqual(report['additional_inference_authorized'],0)
            self.assertFalse((root/'followups'/CAMPAIGN).exists());self.assertEqual(protect.read_bytes(),b'mock original')
            self.assertEqual(sorted(p.name for p in out.iterdir()),['offline_preparation.json'])
    def test_offline_output_cannot_nest_inside_a_protected_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);assets=root/'assets';assets.mkdir()
            setup=root/'v2.json';write_json(setup,{'asset_root':str(assets)})
            build=root/'build.json';write_json(build,{})
            with patch('finocr_qualification.preparation.frozen_reference',return_value={}), \
                 patch('finocr_qualification.preparation.mandatory_paths',return_value=[assets]):
                with self.assertRaises(ValueError):prepare_offline(REPO,setup,root,root,build,assets/'forbidden')
            self.assertEqual(list(assets.iterdir()),[])
    def test_invalid_preparation_cannot_be_used_as_authorization(self):
        with self.assertRaises((ValueError,KeyError)):
            validate_preparation({'kind':'execution_ticket'},REPO)


class TransportAdapterTests(unittest.TestCase):
    def test_exact_ordered_wire_is_used_by_actual_stream_helper_with_mock_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);backend=WindowsBackend({},root,root);backend.base='http://127.0.0.1:1';backend.guard=Mock()
            opened=Mock();opened.open.return_value=io.BytesIO(b'data: mock fixture\n\n')
            payload=request_payload([1,2])
            with patch('urllib.request.build_opener',return_value=opened):backend.complete(payload,root)
            self.assertEqual(opened.open.call_args[0][0].data,wire(payload))
            self.assertEqual((root/'raw-response.sse').read_bytes(),b'data: mock fixture\n\n')
            self.assertEqual(json.loads((root/'transport.json').read_text())['status'],'received')
    def test_actual_stream_transport_failure_saves_error_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);backend=WindowsBackend({},root,root);backend.base='http://127.0.0.1:1';backend.guard=Mock()
            opened=Mock();opened.open.side_effect=OSError('mock network failure')
            with patch('urllib.request.build_opener',return_value=opened):
                with self.assertRaises(ValueError):backend.complete(request_payload([1]),root)
            self.assertEqual(opened.open.call_count,1)
            self.assertEqual(json.loads((root/'transport.json').read_text())['status'],'terminal_failure')
    def test_parent_total_deadline_stops_owned_server_and_retains_partial_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_bytes(root/'raw-response.sse',b'mock partial')
            backend=WindowsBackend({},root,root);backend.base='http://127.0.0.1:1';backend.guard=Mock();backend.process=Mock()
            thread=Mock();thread.is_alive.side_effect=[True,False]
            with patch('finocr_qualification.backend.threading.Thread',return_value=thread), \
                 patch('finocr_qualification.backend.time.monotonic',side_effect=[0,181,182]), \
                 patch('finocr_qualification.backend.stop_process') as stop:
                with self.assertRaises(TimeoutError):backend.complete(request_payload([1]),root)
            stop.assert_called_once_with(backend.process)
            self.assertEqual((root/'raw-response.sse').read_bytes(),b'mock partial')
    def test_metadata_uses_ordered_serializer_and_only_loopback_mock(self):
        backend=WindowsBackend({},REPO,REPO);backend.base='http://127.0.0.1:1';backend.guard=Mock()
        opened=Mock();opened.open.return_value=io.BytesIO(b'{"prompt":"mock"}')
        with patch('urllib.request.build_opener',return_value=opened):backend.metadata('/apply-template',{'json_schema':SCHEMA})
        self.assertEqual(opened.open.call_args[0][0].data,wire({'json_schema':SCHEMA}))


class ResourceAndRuntimeTests(unittest.TestCase):
    def test_device_driver_capacity_and_vram_are_strict(self):
        self.assertEqual(device_reading('0,NVIDIA GeForce RTX 3070 Ti,537.70,8192,7168')['used_mib'],7168)
        for text in ['0,NVIDIA GeForce RTX 3070 Ti,537.70,8192,7169',
                     '0,NVIDIA GeForce RTX 3070 Ti,999,8192,10',
                     '0,NVIDIA GeForce RTX 3060,537.70,8192,10','0,x,537.70,8192,1\n1,x,537.70,8192,1']:
            with self.assertRaises(ValueError):device_reading(text)
    def test_ram_thresholds_and_invalid_measurements(self):
        good={'server_rss_bytes':GIB,'client_rss_bytes':GIB,'system_available_bytes':2*GIB,'system_total_bytes':16*GIB}
        check_sample(good)
        for change in [{'server_rss_bytes':8*GIB},{'system_available_bytes':2*GIB-1},{'client_rss_bytes':0}]:
            with self.assertRaises(ValueError):check_sample({**good,**change})
    def test_disk_ram_preflight_needs_existing_resources_only(self):
        psutil=Mock();psutil.virtual_memory.return_value=Mock(available=GIB,total=16*GIB)
        with patch.dict(sys.modules,{'psutil':psutil}),patch('shutil.disk_usage',return_value=Mock(free=6*GIB)):
            with self.assertRaises(ValueError):preflight_resources(REPO)
    def test_fa_auto_runtime_drift_and_last_offload_are_rejected(self):
        log='flash_attn = disabled\noffloaded 37/37 layers\nVulkan0 RTX 3070 Ti\nn_ctx = 6144\nn_ctx_per_seq = 6144\nn_seq_max = 1\nn_batch = 512\nn_ubatch = 128\nK (f16) V (f16)\n'
        self.assertTrue(runtime_log(log)['full_gpu_offload'])
        for suffix in ['Flash Attention was auto, set to enabled\n','offloaded 12/37 layers\n','VK_ERROR_DEVICE_LOST\n','n_ctx = 8192\n']:
            with self.assertRaises(ValueError):runtime_log(log+suffix)
    def test_metadata_allowlist_blocks_completion_route(self):
        backend=WindowsBackend({},REPO,REPO)
        with self.assertRaises(ValueError):backend.metadata('/completion',{})
    def test_resource_worker_failure_stops_owned_process(self):
        monitor=ResourceMonitor.__new__(ResourceMonitor);monitor.done=Mock()
        monitor.done.wait.side_effect=[False,True];monitor.sample=Mock(side_effect=ValueError('mock threshold'))
        monitor.errors=[];monitor.owned_process=Mock()
        with patch('finocr_answer.feasibility.stop_process') as stop:monitor._loop()
        stop.assert_called_once_with(monitor.owned_process);self.assertTrue(monitor.errors)
    def test_stale_resource_samples_fail_guard(self):
        monitor=ResourceMonitor.__new__(ResourceMonitor);monitor.errors=[];monitor.samples=[{}];monitor.last_sample=0
        with patch('finocr_qualification.resources.time.monotonic',return_value=7):
            with self.assertRaises(ValueError):monitor.guard()
    def test_low_disk_capacity_stops_offline_resource_preflight(self):
        psutil=Mock();psutil.virtual_memory.return_value=Mock(available=4*GIB,total=16*GIB)
        with patch.dict(sys.modules,{'psutil':psutil}),patch('shutil.disk_usage',return_value=Mock(free=5*GIB-1)):
            with self.assertRaises(ValueError):preflight_resources(REPO)


if __name__=='__main__':unittest.main()
