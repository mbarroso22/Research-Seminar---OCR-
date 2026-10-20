"""Offline-only approval fixtures. Fixed trust paths and transports are mocked.

No production approval, allowance, campaign, backend or model is created.
"""
import copy
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from finocr_answer.contract import canonical,digest
from finocr_answer.pause import InferencePausedError
from finocr_qualification.authorization import (AUTHORIZATION_VERSION,LIMITS,AuthorizationRejected,
    VerifiedAuthorization,verify_authorization,revalidate_authorization,guard_authorization_window,_bindings)
from finocr_qualification.evidence import snapshot,write_bytes,write_json
from finocr_qualification.preparation import CAMPAIGN,VERSION,frozen_reference
from finocr_qualification.runner import run,_engine

REPO=Path(__file__).resolve().parents[1]


def load_script(name):
    spec=importlib.util.spec_from_file_location('offline_'+name,REPO/'scripts'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class AuthorizationFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        authdir=self.base/'authorizations';authdir.mkdir()
        self.approval=authdir/(CAMPAIGN+'.approval.json')
        self.authorization=authdir/(CAMPAIGN+'.authorization.json')
        (self.base/'followups').mkdir();self.root=self.base/'followups'/CAMPAIGN
        self.preparation=self.base/'offline-preparation.json'
        self.build=self.base/'mock-native-build.json';write_json(self.build,{'executable_sha256':'a'*64})
        old=self.base/'mock-history';old.write_bytes(b'EXHAUSTED MOCK HISTORY')
        self.ref=frozen_reference(REPO)
        self.impl={'fingerprint':'b'*64,'files':{'mock-only.py':'c'*64},'head':'MOCK-ONLY','dirty_status':''}
        protected=snapshot([old])
        self.report={'kind':'qualification_offline_preparation_not_authorization','version':VERSION,
            'status':'offline_ready_for_separate_review_not_authorization','repository':str(REPO),
            'execution_enabled':False,'benchmark_generation_enabled':False,'inference_executed':0,
            'additional_inference_authorized':0,'remaining_authorized_requests':0,
            'preservation_pass':True,'protected':protected,'preserved_after':protected,
            'historical':{'requests_spent':12,'remaining_authorized':0,'v2_mechanical_pass':'1/6'},
            'frozen_reference':self.ref,'runtime':self.ref['runtime'],'implementation':self.impl,
            'native_build':str(self.build),'campaign_root':str(self.root)}
        self.report['preservation_closeout']={'tracked_files':184,'environment_inventories':3,'mock_only':True}
        write_json(self.preparation,self.report)
        self.record={'kind':'qualification_explicit_authorization','version':AUTHORIZATION_VERSION,
            'authorization_id':'MOCK-ONLY-NOT-AUTHORIZATION','approval_reference':'MOCK HUMAN REFERENCE',
            'issued_at_utc':'2026-10-19T00:00:00Z','expires_at_utc':'2026-10-20T00:00:00Z',
            'explicit_human_authorization':True,'limits':copy.deepcopy(LIMITS),
            'bindings':_bindings(self.preparation,self.preparation.read_bytes(),self.report,REPO,self.ref)}
        self.stack=ExitStack()
        self.stack.enter_context(patch('finocr_qualification.authorization.approval_paths',
            return_value=(self.approval,self.authorization)))
        self.stack.enter_context(patch('finocr_qualification.authorization.implementation',return_value=self.impl))
        self.stack.enter_context(patch('finocr_qualification.authorization._now',
            return_value=datetime(2026,10,19,12,tzinfo=timezone.utc)))
        self.seal_mock()
    def tearDown(self):self.stack.close();self.temp.cleanup()
    def seal_mock(self):
        # Only disposable test fixtures. No issuer exists in production code.
        from hashlib import sha256
        self.authorization.write_bytes(canonical(self.record)+b'\n')
        self.pin={'kind':'qualification_operator_approval','version':AUTHORIZATION_VERSION,
            'approval_reference':self.record['approval_reference'],'authorization_path':str(self.authorization),
            'authorization_file_sha256':sha256(self.authorization.read_bytes()).hexdigest(),
            'approved_at_utc':'2026-10-19T01:00:00Z'}
        self.approval.write_bytes(canonical(self.pin)+b'\n')
    def verify(self):return verify_authorization(self.preparation,REPO,self.authorization)
    def assert_rejected_without_effects(self,call=None):
        before=snapshot([self.base]);backend=Mock(side_effect=AssertionError('No real backend'))
        with patch('finocr_qualification.runner.WindowsBackend',backend), \
             patch('finocr_qualification.runner.Journal',side_effect=AssertionError('No claim')):
            with self.assertRaises(AuthorizationRejected):(call or self.verify)()
        self.assertEqual(before,snapshot([self.base]));self.assertFalse(self.root.exists());backend.assert_not_called()
    def test_exact_mock_binding_verifies_read_only_and_preserves_historical_zero_remaining(self):
        before=snapshot([self.base]);verified=self.verify()
        self.assertIsInstance(verified,VerifiedAuthorization);self.assertEqual(verified.report,self.report)
        self.assertEqual(verified.identity['limits'],LIMITS);self.assertEqual(before,snapshot([self.base]))
        self.assertEqual(verified.report['remaining_authorized_requests'],0);self.assertFalse(self.root.exists())
    def test_default_public_call_pauses_before_any_approval_or_preparation_reads(self):
        with patch('finocr_qualification.authorization._read',side_effect=AssertionError('No reads')), \
             patch('finocr_qualification.runner._engine',side_effect=AssertionError('No execution')):
            with self.assertRaises(InferencePausedError):run(Path('absent'),REPO)
    def test_missing_operator_pin_preserves_genuine_pause_even_when_authorization_supplied(self):
        self.approval.unlink()
        with patch('finocr_qualification.authorization._read',side_effect=AssertionError('No reads')):
            with self.assertRaises(InferencePausedError):run(Path('absent'),REPO,self.authorization)
        self.assertFalse(self.root.exists())
    def test_missing_record_or_preparation_rejects_before_claim(self):
        self.authorization.unlink();self.assert_rejected_without_effects()
        self.seal_mock();self.preparation.unlink();self.assert_rejected_without_effects()
    def test_unreviewed_alternate_record_path_is_rejected_even_with_identical_bytes(self):
        alias=self.base/'same-record.json';alias.write_bytes(self.authorization.read_bytes())
        self.assert_rejected_without_effects(lambda:verify_authorization(self.preparation,REPO,alias))
    def test_altered_record_bytes_fail_the_separate_operator_pin(self):
        self.authorization.write_bytes(self.authorization.read_bytes()+b' ')
        self.assert_rejected_without_effects()
    def test_altered_preparation_bytes_fail_even_when_logical_json_is_unchanged(self):
        self.preparation.write_bytes(self.preparation.read_bytes()+b' ')
        self.assert_rejected_without_effects()
    def test_every_bound_identity_mismatch_is_rejected_without_claim(self):
        original=copy.deepcopy(self.record)
        for key in original['bindings']:
            with self.subTest(binding=key):
                self.record=copy.deepcopy(original);self.record['bindings'][key]='MISMATCH'
                self.seal_mock();self.assert_rejected_without_effects()
    def test_changed_git_state_or_code_cannot_reuse_the_preparation(self):
        for key in ['head','dirty_status','fingerprint','files']:
            with self.subTest(key=key),patch('finocr_qualification.authorization.implementation',
                    return_value={**self.impl,key:'MISMATCH'}):self.assert_rejected_without_effects()
    def test_contract_runtime_or_preservation_mutation_cannot_be_resealed_as_ready(self):
        for key,value in [('runtime',{}),('frozen_reference',{}),('preservation_pass',False),
                          ('preserved_after',{}),('remaining_authorized_requests',6),('inference_executed',False),
                          ('version','qualification-runner-v1-offline')]:
            with self.subTest(key=key):
                changed={**self.report,key:value};self.preparation.write_bytes(canonical(changed)+b'\n')
                self.assert_rejected_without_effects()
    def test_expired_future_or_undated_approval_is_rejected(self):
        for key,value in [('expires_at_utc','2026-10-19T02:00:00Z'),
                ('issued_at_utc','2026-10-19T13:00:00Z'),('expires_at_utc','2026-10-20')]:
            with self.subTest(key=key):
                old=self.record[key];self.record[key]=value;self.seal_mock()
                self.assert_rejected_without_effects();self.record[key]=old
    def test_attempt_retry_order_output_or_boolean_limit_changes_fail(self):
        original=copy.deepcopy(self.record)
        for key,value in [('maximum_completion_attempts',7),('campaigns',True),('retries',1),
                ('resume',True),('case_order',list(reversed(LIMITS['case_order']))),
                ('output_tokens_per_attempt',2048),('request_deadline_seconds',181),('financebench_requests',1)]:
            with self.subTest(key=key):
                self.record=copy.deepcopy(original);self.record['limits'][key]=value
                self.seal_mock();self.assert_rejected_without_effects()
    def test_extra_fields_invalid_json_or_non_explicit_consent_are_rejected(self):
        self.record['allow_any_model']=True;self.seal_mock();self.assert_rejected_without_effects()
        del self.record['allow_any_model'];self.record['explicit_human_authorization']='true'
        self.seal_mock();self.assert_rejected_without_effects()
        self.approval.write_bytes(b'{invalid');self.assert_rejected_without_effects()
    def test_reused_fixed_anchor_rejects_without_reopening_or_backend_calls(self):
        self.root.mkdir();marker=self.root/'mock-consumed';marker.write_bytes(b'KEEP')
        before=snapshot([self.base])
        with self.assertRaises(AuthorizationRejected):self.verify()
        self.assertEqual(before,snapshot([self.base]));self.assertEqual(marker.read_bytes(),b'KEEP')
    def test_symlink_record_is_rejected_without_following_to_execution(self):
        raw=self.authorization.read_bytes();self.authorization.unlink()
        target=self.base/'target-record.json';target.write_bytes(raw)
        # Mock link metadata for portability: Windows tests need no symlink privilege.
        original=Path.is_symlink
        before=snapshot([self.base])
        with patch.object(Path,'is_symlink',lambda p:p==self.authorization or original(p)):
            with self.assertRaises(AuthorizationRejected):self.verify()
        self.assertEqual(before,snapshot([self.base]));self.assertFalse(self.root.exists())
    def test_mutation_after_verification_is_rejected_before_engine_claim(self):
        verified=self.verify();self.approval.write_bytes(self.approval.read_bytes()+b' ')
        self.assert_rejected_without_effects(lambda:_engine(self.report,REPO,verified,factory=Mock()))
    def test_forged_reference_or_changed_in_memory_report_cannot_enter_engine(self):
        self.assert_rejected_without_effects(lambda:_engine(self.report,REPO,'NONEMPTY-IS-NOT-APPROVAL'))
        verified=self.verify()
        self.assert_rejected_without_effects(lambda:revalidate_authorization(verified,{**self.report,'changed':True},REPO))
    def test_approved_mock_dispatch_uses_verified_report_and_no_real_transport(self):
        result={'status':'MOCK-ONLY'}
        with patch('finocr_qualification.runner._engine',return_value=result) as engine:
            self.assertEqual(run(self.preparation,REPO,self.authorization),result)
        self.assertIsInstance(engine.call_args.args[2],VerifiedAuthorization);self.assertFalse(self.root.exists())
    def test_live_window_rejects_a_new_submission_after_expiry(self):
        verified=self.verify();guard_authorization_window(verified)
        with patch('finocr_qualification.authorization._now',
                return_value=datetime(2026,10,20,1,tzinfo=timezone.utc)):
            with self.assertRaises(AuthorizationRejected):guard_authorization_window(verified)
        self.assertFalse(self.root.exists())


class QualificationCLIStatusTests(unittest.TestCase):
    def setUp(self):self.cli=load_script('run_qualification.py')
    def invoke(self,*,result=None,error=None):
        with patch('sys.argv',['run_qualification.py','--preparation','absent']), \
             patch.object(self.cli,'run',return_value=result,side_effect=error),redirect_stdout(io.StringIO()) as stream:
            code=self.cli.main()
        return code,json.loads(stream.getvalue())
    def test_success_status_means_only_completed_automated_checks_with_verified_export(self):
        result={'status':'completed_manual_review_pending','automated_checks_pass':True,
                'qualification_pass':False,'export':{'verified':True}}
        code,data=self.invoke(result=result);self.assertEqual(code,0);self.assertFalse(data['qualification_pass'])
    def test_mechanical_terminal_export_and_unknown_outcomes_have_distinct_nonzero_statuses(self):
        for status,expected in [('completed_mechanical_failures_manual_review_pending',6),
                ('terminal_stop',5),('preflight',1)]:
            with self.subTest(status=status):
                code,_=self.invoke(result={'status':status,'export':{'verified':True}});self.assertEqual(code,expected)
        for result in [{'status':'completed_manual_review_pending','automated_checks_pass':True},
                {'status':'terminal_stop','export_error':'MOCK EXPORT FAILURE'}]:
            self.assertEqual(self.invoke(result=result)[0],7)
    def test_pause_and_rejected_authorization_are_distinct_and_start_no_campaign(self):
        self.assertEqual(self.invoke(error=InferencePausedError('MOCK PAUSE'))[0],2)
        code,data=self.invoke(error=AuthorizationRejected('MOCK MISMATCH'))
        self.assertEqual(code,3);self.assertFalse(data['campaign_created_this_invocation'])
    def test_unexpected_post_dispatch_error_does_not_fabricate_zero_spending(self):
        code,data=self.invoke(error=OSError('MOCK EVIDENCE WRITE FAILURE'))
        self.assertEqual(code,1);self.assertNotIn('inference_executed',data)
        self.assertEqual(data['attempt_count'],'inspect_preserved_campaign_evidence')
