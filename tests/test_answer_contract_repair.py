"""Revised-contract conformance only. No model/backend/inference is executed."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
from finocr_answer.contract import CONTRACT_VERSION, SCHEMA, INSTRUCTION, canonical, digest, messages, schema_issues, strict_json, wire
from finocr_answer.conformance import compile_schema, file_snapshot, run_offline, tokenizer_checks
from finocr_answer.conformance_fixtures import positives, negatives, pages
from finocr_answer.grammar import Grammar
from finocr_answer.historical_contract_v2 import SCHEMA as V2_SCHEMA, INSTRUCTION as V2_INSTRUCTION
from finocr_answer.historical_validation_v2 import functional_checks as historical_checks
from finocr_answer.synthetic import cases, historical_cases_v2, pack, pack_historical_v2
from finocr_answer.validation import validate_response, functional_checks
from finocr_answer.pause import InferencePausedError
from finocr_answer.feasibility import post, run, stream_completion
from finocr_answer.followup import prepare_followup
from finocr_answer.setup import seal

REPO=Path(__file__).resolve().parents[1]
GRAMMAR_TEXT=(REPO/'tests/fixtures/answer_contract_v3/schema.gbnf').read_text(encoding='utf-8')


class ContractRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.grammar=Grammar(GRAMMAR_TEXT)
    def test_status_and_quantity_discriminators_survive_full_wire_envelope(self):
        request={'json_schema':SCHEMA,'prompt':[10,20]}
        encoded=wire(request);schema=strict_json(encoded)['json_schema']
        for branch in schema['anyOf']:self.assertEqual(next(iter(branch['properties'])),'status')
        for branch in schema['anyOf'][0]['properties']['quantities']['items']['anyOf']:
            self.assertEqual(next(iter(branch['properties'])),'unit')
        self.assertEqual(digest(request),hashlib.sha256(canonical(request)).hexdigest())
        self.assertNotEqual(wire(request),canonical(request))
        self.assertEqual(list(strict_json(canonical(request))['json_schema']['anyOf'][0]['properties'])[-1],'status')
    def test_versioned_schema_instruction_cases_and_grammar_identities_are_consistent(self):
        identity=strict_json((REPO/'tests/fixtures/answer_contract_v3/identity.json').read_text())
        self.assertEqual(identity['schema_wire_sha256'],hashlib.sha256(wire(SCHEMA)).hexdigest())
        self.assertEqual(identity['schema_canonical_sha256'],digest(SCHEMA))
        self.assertEqual(identity['grammar_sha256'],hashlib.sha256(GRAMMAR_TEXT.encode()).hexdigest())
        self.assertEqual(identity['instruction_sha256'],hashlib.sha256(INSTRUCTION.encode()).hexdigest())
        self.assertEqual(identity['cases_sha256'],digest(cases()))
    def test_revised_packing_preserves_candidates_body_prefixes_and_capacity_caps(self):
        # Standard-library-only reversible test tokenizer; not the model tokenizer.
        class Tokenizer:
            def __init__(self):self.values={};self.inverse={}
            def encode(self,text,add_special_tokens=False):
                tokens=[]
                for i in range(0,len(text),4):
                    part=text[i:i+4]
                    if part not in self.values:
                        k=len(self.values);self.values[part]=k;self.inverse[k]=part
                    tokens.append(self.values[part])
                return tokens
            def decode(self,tokens,**kwargs):return ''.join(self.inverse[k] for k in tokens)
            def apply_chat_template(self,turns,**kwargs):return ''.join(f"<{t['role']}>"+t['content']+f"</{t['role']}>" for t in turns)+'<assistant>'
        tokenizer=Tokenizer();records=tokenizer_checks(tokenizer)['cases']
        self.assertEqual(records[-1]['input_tokens'],5120);self.assertEqual(records[-1]['evidence_tokens'],4096)
        self.assertEqual(records[-1]['overhead_tokens'],1024);self.assertEqual(records[-1]['body_tokens'],[800]*5)
        for current,old in zip(cases(),historical_cases_v2()):
            _,a=pack(current,tokenizer);_,b=pack_historical_v2(old,tokenizer)
            self.assertEqual(a['retained'],b['retained']);self.assertEqual([p['page_id'] for p in a['retained']],list(range(5)))
    def test_metadata_post_uses_wire_serializer_not_canonical_sort(self):
        opened=Mock();opened.open.return_value=io.BytesIO(b'{}')
        with patch('urllib.request.build_opener',return_value=opened):post('http://127.0.0.1:1/apply-template',{'json_schema':SCHEMA})
        self.assertEqual(opened.open.call_args[0][0].data,wire({'json_schema':SCHEMA}))
    def test_stream_transport_uses_same_exact_ordered_bytes(self):
        opened=Mock();opened.open.return_value=io.BytesIO(b'data: {"stop":true}\n\n')
        with tempfile.TemporaryDirectory() as tmp,patch('urllib.request.build_opener',return_value=opened):
            r=stream_completion('http://127.0.0.1:1/completion',{'json_schema':SCHEMA},Path(tmp)/'raw',Mock())
        self.assertEqual(r['status'],'received');self.assertEqual(opened.open.call_args[0][0].data,wire({'json_schema':SCHEMA}))
    def test_handwritten_positive_responses_pass_actual_grammar_and_mechanics(self):
        for name,value in positives().items():
            with self.subTest(name=name):
                self.assertFalse(schema_issues(value));self.assertTrue(self.grammar.accepts(wire(value).decode()))
                result=functional_checks(value,name,pages(name));self.assertTrue(result['mechanical_pass'],result['issues'])
                self.assertEqual(result['contract_version'],CONTRACT_VERSION);self.assertFalse(result['fully_supported_pass'])
    def test_every_adversarial_fixture_stays_a_failure(self):
        for label,name,value in negatives():
            with self.subTest(label=label):self.assertFalse(functional_checks(value,name,pages(name))['mechanical_pass'])
    def test_dimension_tuples_are_rejected_in_both_schema_and_grammar(self):
        for fields in [{'unit':'percent'},{'currency':'none'},{'unit':'ratio','currency':'none','scale':'million'}]:
            r=positives()['signed'];r['quantities'][0].update(fields)
            self.assertTrue(schema_issues(r));self.assertFalse(self.grammar.accepts(wire(r).decode()))
        r=positives()['margin'];r['quantities'][2]['scale']='percent'
        self.assertFalse(self.grammar.accepts(wire(r).decode()))
    def test_answered_reserved_marker_rejected_in_both_directions(self):
        for marker in ['insufficient_evidence',' INSUFFICIENT_EVIDENCE ']:
            r=positives()['signed'];r['answer']=marker
            self.assertIn('abstention_conflict',{e['code'] for e in validate_response(r,pages('signed'))['issues']})
        r=positives()['capacity'];r['answer']='The ratio is known.'
        self.assertFalse(validate_response(r,pages('capacity'))['mechanical_pass'])
    def test_abstention_cannot_assert_a_claim_quantity_calculation_or_blank_missing_fact(self):
        good=positives()
        for key,value in [('claims',good['signed']['claims']),('quantities',good['signed']['quantities']),
                          ('calculation',good['scale']['calculation']),('missing_information',[' '])]:
            r=copy.deepcopy(good['capacity']);r[key]=value
            self.assertFalse(validate_response(r,pages('capacity'))['mechanical_pass'])
    def test_capacity_question_is_prospectively_a_calculation_task(self):
        revised,old=cases(),historical_cases_v2()
        self.assertEqual(revised[:5],old[:5]);self.assertNotEqual(revised[-1]['question'],old[-1]['question'])
        self.assertTrue(revised[-1]['question'].startswith('Calculate '));self.assertTrue(old[-1]['question'].startswith('Can '))
        self.assertEqual([c['pages'] for c in revised],[c['pages'] for c in old])
        self.assertTrue(functional_checks(positives()['capacity'],'capacity',pages('capacity'))['mechanical_pass'])
    def test_prompt_explicitly_matches_representation_rules_without_expected_answers(self):
        for fragment in ['Choose status first','status and answer must both be insufficient_evidence','every requested numerical result',
                         'Numeric conversion constants','For selection/narrative','prior margin, current margin','first requested calculation']:
            self.assertIn(fragment,INSTRUCTION)
        for expected_answer in ['12.5','1250','240','180','Cedar Works','scale_factor','financebench']:
            self.assertNotIn(expected_answer,INSTRUCTION)
    def test_calculation_result_must_also_be_a_typed_quantity(self):
        r=positives()['scale'];r['quantities'].pop()
        self.assertIn('calculation_result_quantity',{e['code'] for e in functional_checks(r,'scale',pages('scale'))['issues']})
    def test_all_margin_components_stay_required(self):
        r=positives()['margin'];r['quantities']=r['quantities'][:3]
        result=functional_checks(r,'margin',pages('margin'))
        self.assertFalse(result['mechanical_pass']);self.assertFalse(result['quantity_3']);self.assertFalse(result['quantity_4'])
    def test_correct_arithmetic_does_not_excuse_unlinked_or_undefined_operands(self):
        r=positives()['margin'];r['calculation']['expression']='(240-180)/240*100'
        result=functional_checks(r,'margin',pages('margin'))
        self.assertTrue(result['arithmetic_25_percent']);self.assertFalse(result['mechanical_pass'])
        r=positives()['scale'];r['calculation']['operand_ids'].append('scale_factor')
        self.assertIn('undefined_operand',{e['code'] for e in functional_checks(r,'scale',pages('scale'))['issues']})
    def test_literal_but_irrelevant_support_never_becomes_verified_support(self):
        r=positives()['signed'];r['claims'][0]['text']='Profit improved for an unrelated reason.'
        result=validate_response(r,pages('signed'))
        self.assertEqual(result['semantic_support'],'pending_manual_review');self.assertFalse(result['fully_supported_pass'])
        # Literal validity is deliberately not an entailment/financial correctness judge.
        self.assertTrue(result['mechanical_pass'])
    def test_number_lexing_is_not_repaired_and_sign_year_scale_remain_checked(self):
        for value in ['value: -12.5','$-12.5','1,25','NaN','1e3','(-12.5)']:
            r=positives()['signed'];r['quantities'][0]['value']=value
            self.assertFalse(functional_checks(r,'signed',pages('signed'))['mechanical_pass'])
        for field,value in [('value','12.5'),('fiscal_year','2030'),('scale','thousand')]:
            r=positives()['signed'];r['quantities'][0][field]=value
            self.assertFalse(functional_checks(r,'signed',pages('signed'))['mechanical_pass'])
    def test_label_exclusion_and_zero_based_pages_stay_strict(self):
        c=cases()[0]
        for key in ['answers','justification','evidence_pages','scores','expanded_query','expected_status']:
            with self.assertRaises(ValueError):messages({**c,key:'must not enter model context'})
        for identifier in [-1,False]:
            r=positives()['signed'];r['claims'][0]['support'][0]['page_id']=identifier
            self.assertFalse(validate_response(r,pages('signed'))['mechanical_pass'])


class HistoricalAndPauseTests(unittest.TestCase):
    def test_frozen_v2_schema_instruction_and_case_are_not_replaced(self):
        self.assertEqual(digest(V2_SCHEMA),'abd2797aec68a067353628bbe479511c079ed8b0003484e552a1642c44410041')
        self.assertEqual(hashlib.sha256(V2_INSTRUCTION.encode()).hexdigest(),'8ba2802f2dfc37c1ebc829bd71fd17069bba2ef21ae269f5f8e61ea149e8046d')
        self.assertNotEqual(digest(SCHEMA),digest(V2_SCHEMA));self.assertNotEqual(INSTRUCTION,V2_INSTRUCTION)
    def test_original_raw_fixture_bytes_and_v2_diagnostics_are_exact(self):
        directory=REPO/'tests/fixtures/answer_feasibility_v2';hashes=strict_json((directory/'source-hashes.json').read_text())['raw_content_sha256']
        original=strict_json((directory/'recorded-checks.json').read_text())
        for name,expected in hashes.items():
            self.assertEqual(hashlib.sha256((directory/(name+'.json')).read_bytes()).hexdigest(),expected)
            value=strict_json((directory/(name+'.json')).read_text());self.assertEqual(historical_checks(value,name,pages(name)),original[name])
    def test_genuine_failures_in_both_original_campaigns_remain_rejected(self):
        for version in ['v1','v2']:
            root=REPO/('tests/fixtures/answer_feasibility_'+version)
            for name in ['signed','scale','margin','comparison','capacity']:
                with self.subTest(version=version,name=name):
                    r=strict_json((root/(name+'.json')).read_text())
                    self.assertFalse(functional_checks(r,name,pages(name))['mechanical_pass'])
                    self.assertFalse(historical_checks(r,name,pages(name))['mechanical_pass'])
    def test_run_followup_and_seal_are_paused_before_any_io_or_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ledger=root/'synthetic_campaign.json';ledger.write_text('preserve exact old ledger')
            before=file_snapshot([root])
            with patch('subprocess.Popen',side_effect=AssertionError('No process')),patch('pathlib.Path.read_text',side_effect=AssertionError('No setup read')):
                for call in [lambda:run(root/'absent',root/'newrun',root),lambda:prepare_followup(root/'absent',ledger,root/'oldrun',root),lambda:seal({},root/'newassets',root)]:
                    with self.assertRaises(InferencePausedError):call()
            self.assertEqual(file_snapshot([root]),before)
    def test_environment_variable_cannot_enable_inference(self):
        with patch.dict(os.environ,{'FINOCR_ALLOW_INFERENCE':'1','FINOCR_REQUEST_BUDGET':'999'}):
            with self.assertRaises(InferencePausedError):run(Path('missing'),Path('unused'),REPO)
    def test_paused_clis_fail_without_creating_outputs_or_tickets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for script,args in [('run_answer_feasibility.py',['--setup',str(root/'absent'),'--output',str(root/'run')]),
                ('prepare_answer_followup.py',['--previous-setup',str(root/'absent'),'--previous-campaign',str(root/'ledger'),'--previous-run',str(root/'old')])]:
                result=subprocess.run([sys.executable,str(REPO/'scripts'/script),*args],env={**os.environ,'PYTHONPATH':str(REPO/'src')},capture_output=True,text=True)
                self.assertEqual(result.returncode,2,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'inference_paused')
            self.assertEqual(list(root.iterdir()),[])


class PortableGrammarTests(unittest.TestCase):
    def test_earley_literals_ranges_repetition_union_epsilon_and_unicode(self):
        g=Grammar('root ::= "{" (word ",")? [0-9]{1,3} "}"\nword ::= "−" | "amount"\n')
        for value in ['{0}','{123}','{−,12}','{amount,1}']:self.assertTrue(g.accepts(value))
        for value in ['{}','{1234}','{amount}','{?,1}','{12}junk']:self.assertFalse(g.accepts(value))
    def test_unsupported_or_undefined_grammar_fails_closed(self):
        for text in ['root ::= missing','root ::= .','root ::= "x"{3,1}','root ::= [\\d]','root ::= "unterminated']:
            with self.assertRaises(ValueError):Grammar(text)
    def test_status_first_grammar_rejects_reordered_output(self):
        g=Grammar(GRAMMAR_TEXT);r=positives()['signed']
        self.assertTrue(g.accepts(wire(r).decode()));self.assertFalse(g.accepts(canonical(r).decode()))


class OfflineGateTests(unittest.TestCase):
    def test_converter_source_and_commit_verification_precedes_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'examples').mkdir();(root/'examples/json_schema_to_grammar.py').write_text('changed')
            with patch('subprocess.check_output',return_value='wrong'),patch('subprocess.run') as execute:
                with self.assertRaises(ValueError):compile_schema(root,root/'schema.json')
                execute.assert_not_called()
    def test_offline_gate_writes_no_ticket_and_preserves_protected_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old';old.mkdir();(old/'ledger').write_bytes(b'exhausted')
            before=file_snapshot([old]);out=root/'review'
            with patch('finocr_answer.conformance.compile_schema',return_value=GRAMMAR_TEXT.encode()):
                r=run_offline(REPO,root/'source',out,protected=[old])
            self.assertEqual(r['inference_executed'],0);self.assertEqual(r['additional_inference_authorized'],0)
            self.assertEqual(r['remaining_authorized_requests'],0);self.assertEqual(r['tokenizer_check']['status'],'not_run')
            self.assertEqual(before,file_snapshot([old]));self.assertTrue((out/'offline_conformance.json').exists())
            self.assertFalse(any(out.rglob('synthetic_campaign.json')));self.assertFalse(any(out.rglob('setup_manifest.json')))
            with self.assertRaises(FileExistsError):run_offline(REPO,root/'source',out,protected=[old])
    def test_protected_or_repository_nested_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);protected=root/'assets';protected.mkdir()
            for out in [protected/'newreview',REPO/'temporary-review']:
                with self.assertRaises(ValueError):run_offline(REPO,root/'source',out,protected=[protected])
            with self.assertRaises(ValueError):run_offline(REPO,root/'source',root/'tokenizer/review',read_only_roots=[root/'tokenizer'])
    def test_converter_failure_retains_failure_report_without_touching_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'ledger';old.write_bytes(b'old');out=root/'review'
            with patch('finocr_answer.conformance.compile_schema',side_effect=ValueError('Unsupported grammar feature')):
                with self.assertRaises(ValueError):run_offline(REPO,root/'source',out,protected=[old])
            r=json.loads((out/'offline_conformance.json').read_text())
            self.assertEqual(r['status'],'failed');self.assertTrue(r['protected_artifacts_unchanged']);self.assertEqual(old.read_bytes(),b'old')


if __name__=='__main__':unittest.main()
