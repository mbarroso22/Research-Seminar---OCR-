"""Frozen historical-v2 regressions; runner tests use fully simulated I/O and a mocked pause guard."""
import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock,patch

from finocr_answer.audit import audit_original, audit_to_directory, snapshot, LEGACY_SCHEMA_SHA, LEGACY_INSTRUCTION_SHA
from finocr_answer.backend import EXECUTION, require_settings, observe_settings
from finocr_answer.historical_contract_v2 import SCHEMA,INSTRUCTION,VERSION,canonical,digest,strict_json,validate_schema
from finocr_answer.followup import BUDGET,followup_root,prepare_followup,validate_followup_setup,require_lineage
from finocr_answer.setup import identity,sha
from finocr_answer.synthetic import historical_cases_v2 as cases
from finocr_answer.historical_contract_v2 import messages
from finocr_answer.historical_validation_v2 import functional_checks,validate_response
from finocr_answer.feasibility import run
from finocr.io import write_json

FIXTURES=Path(__file__).parent/'fixtures/answer_feasibility_v1'
AUTO_LOG='''offloaded 37/37 layers to GPU; Vulkan0: RTX 3070 Ti
n_ctx = 6144
n_ctx_per_seq = 6144
n_seq_max = 1
n_batch = 512
n_ubatch = 128
flash_attn = auto
K (f16):432, V (f16):432
Flash Attention was auto, set to enabled
'''
OFF_LOG=AUTO_LOG.replace('flash_attn = auto','flash_attn = disabled').replace('Flash Attention was auto, set to enabled','')


def pages(name):return {p['page_id']:p['raw_text'] for c in cases() if c['task_id']=='synthetic:'+name for p in c['pages']}
def original(name):return strict_json((FIXTURES/(name+'.json')).read_text())
def q(identifier,value,name=None,unit='amount',currency='USD',scale='million',year='2031',span=None,case='signed'):
    return {'id':identifier,'name':name or identifier,'value':value,'unit':unit,'currency':currency,'scale':scale,'fiscal_year':year,
            'source':{'page_id':0,'span':span or pages(case)[0]}}

def valid(name):
    if name in {'missing','capacity'}:
        return {'status':'insufficient_evidence','answer':'insufficient_evidence','claims':[],'quantities':[],
                'calculation':None,'missing_information':['Current liabilities were not supplied.']}
    r={'status':'answered','answer':'Concise fictional answer; semantic review remains required.','claims':[{'text':'Source-supported statement',
       'support':[{'page_id':0,'span':pages(name)[0]}]}],'quantities':[],'calculation':None,'missing_information':[]}
    if name=='signed':r['quantities']=[q('cash','-12.5')]
    if name=='scale':
        r['quantities']=[q('revenue','1.25',scale='billion',case=name),q('converted','1250',case=name)]
        r['calculation']={'expression':'revenue*1000','operand_ids':['revenue'],'result':'1250','unit':'USD million'}
    if name=='comparison':r['quantities']=[q('operations','40',case=name),q('investing','-12',case=name),q('financing','-9',case=name)]
    if name=='margin':
        r['quantities']=[q('revenue','240',case=name),q('cost','180',case=name),
            q('prior','20',unit='percent',currency='none',scale='unit',year='2030',case=name),
            q('current','25',unit='percent',currency='none',scale='unit',case=name),
            q('change','5',unit='percentage_points',currency='none',scale='unit',case=name)]
        r['calculation']={'expression':'(revenue-cost)/revenue*100','operand_ids':['revenue','cost'],'result':'25','unit':'percent'}
    return r


def legacy_fixture(root):
    """Coherent simulated transport artifacts; real outputs copied unchanged above."""
    assets=root/'assets';assets.mkdir();(assets/'converted').mkdir();(assets/'converted/conversion.json').write_text('fixture conversion')
    model=assets/'model.gguf';model.write_bytes(b'fixture model');server=assets/'server.exe';server.write_bytes(b'fixture backend')
    setup=assets/'setup_manifest.json';campaign=assets/'synthetic_campaign.json';run_dir=root/'legacy-run';run_dir.mkdir()
    old={'version':'bounded-answer-preparation-v1','runtime':{},'asset_root':str(assets),
         'instruction_sha256':LEGACY_INSTRUCTION_SHA,'schema_sha256':LEGACY_SCHEMA_SHA,'model':identity(model),'server':identity(server),
         'conversion_sha256':sha(assets/'converted/conversion.json'),'lock':{}}
    write_json(setup,old);schema=strict_json((FIXTURES/'legacy-schema.json').read_text());records=[];hashes=[]
    for case in cases():
        name=case['task_id'].split(':')[1];directory=run_dir/name;directory.mkdir()
        copy_case=copy.deepcopy(case)
        if name=='capacity':
            for page in copy_case['pages']:page['raw_text']=page['raw_text'][:800]+'\n[truncated]'
        turns=messages(copy_case);prompt=''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in turns)+'<|im_start|>assistant\n'
        count=5120 if name=='capacity' else 340
        tokens=list(range(count));payload={'prompt':tokens,'n_predict':1024,'temperature':0,'seed':0,'top_k':1,'top_p':1.0,'min_p':0.0,
            'repeat_penalty':1.0,'presence_penalty':0.0,'frequency_penalty':0.0,'cache_prompt':False,'json_schema':schema,'stream':True,'id_slot':0}
        write_json(directory/'request.json',payload);(directory/'prompt.txt').write_bytes(prompt.encode())
        write_json(directory/'packing.json',{'prompt':prompt,'token_ids':tokens,'input_tokens':count,'evidence_tokens':4096 if name=='capacity' else 100,
            'overhead_tokens':1024 if name=='capacity' else 240,'retained':[{'page_id':p,'retained_interval':[0,800 if name=='capacity' else 0]} for p in range(5)]})
        content=(FIXTURES/(name+'.json')).read_text();parsed=strict_json(content)
        final={'content':content,'stop':True,'tokens_predicted':120,'stop_type':'eos','timings':{'prompt_n':count,'predicted_n':120}}
        raw=('data: '+json.dumps(final)+'\n\n').encode();(directory/'raw-response.sse').write_bytes(raw)
        (directory/'raw-content.txt').write_bytes(content.encode());write_json(directory/'parsed.json',parsed);write_json(directory/'backend-final.json',final)
        request_hash=digest({'model':old['model']['sha256'],'instruction':old['instruction_sha256'],'schema':old['schema_sha256'],
            'backend':old['server']['sha256'],'setup_sha256':sha(setup),'request':payload});hashes.append(request_hash)
        records.append({'case_id':name,'input_tokens':count,'generated_tokens':120,'wall_seconds':.1,'request_sha256':request_hash,
                        'response_sha256':hashlib.sha256(raw).hexdigest(),'checks':{'schema':True}})
    memory={'server_rss_bytes':100,'client_rss_bytes':20,'system_total_bytes':1600,'system_available_bytes':900,
            'gpu_device_wide':'0, NVIDIA GeForce RTX 3070 Ti, 537.70, 8192, 4000'}
    (run_dir/'memory_samples.jsonl').write_text(json.dumps(memory)+'\n')
    (run_dir/'server.stderr.log').write_text(AUTO_LOG)
    write_json(run_dir/'run_manifest.json',{'kind':'synthetic_feasibility_only','primary_requests':0,'annotated_page_requests':0,'benchmark_generation_enabled':False,
        'setup':identity(setup),'request_budget':6,'attempted':6,'records':records,'startup_wall_seconds':.1,'wall_seconds':1,
        'memory':{'sample_count':1,'server_sampled_peak_rss_bytes':100,'client_sampled_peak_rss_bytes':20,'sampled_peak_sum_rss_bytes':120,
            'minimum_system_available_bytes':900,'sampled_peak_system_used_bytes':700,'device_wide_sampled_peak_used_mib':4000,'measurement_errors':[]}})
    write_json(campaign,{'attempted':6,'requests':hashes,'setup_sha256':sha(setup),'output':str(run_dir)})
    return run_dir,setup,campaign


class StrictOutputTests(unittest.TestCase):
    def check(self,value,name='signed'):return functional_checks(value,name,pages(name))
    def test_all_real_saved_failure_outputs_stay_rejected(self):
        for name in ['signed','scale','margin','comparison','capacity']:
            with self.subTest(name=name):self.assertFalse(self.check(original(name),name)['mechanical_pass'])
        self.assertTrue(self.check(original('missing'),'missing')['mechanical_pass'])
    def test_real_fixture_bytes_are_exact_original_output_bytes(self):
        hashes=strict_json((FIXTURES/'source-hashes.json').read_text())['raw_content_sha256']
        for name,expected in hashes.items():self.assertEqual(sha(FIXTURES/(name+'.json')),expected)
    def test_valid_typed_mechanics_pass_without_claiming_semantic_correctness(self):
        for name in ['signed','scale','margin','comparison','missing','capacity']:
            with self.subTest(name=name):
                result=self.check(valid(name),name);self.assertTrue(result['mechanical_pass'],result['issues'])
                self.assertEqual(result['semantic_support'],'pending_manual_review')
    def test_no_numeric_prefix_or_unit_repair(self):
        for number in ['value: -12.5','$-12.5','1,25','NaN','1e3','(-12.5)']:
            r=valid('signed');r['quantities'][0]['value']=number
            self.assertFalse(self.check(r)['mechanical_pass'])
        for unit in ['USD million','million USD','million']:
            r=valid('signed');r['quantities'][0]['unit']=unit
            with self.assertRaises(ValueError):validate_schema(r)
    def test_financing_sign_error_survives_isolated_format_fixes(self):
        r=valid('comparison');r['quantities'][2]['value']='9'
        result=self.check(r,'comparison');self.assertTrue(result['schema']);self.assertFalse(result['mechanical_pass'])
        self.assertIn('activity_value_or_sign',{e['code'] for e in result['issues']})
    def test_percent_is_not_a_scale_and_currency_dimensions_must_agree(self):
        r=valid('margin');r['quantities'][2]['scale']='percent'
        self.assertFalse(self.check(r,'margin')['schema'])
        r['quantities'][2]['scale']='million'
        result=self.check(r,'margin');self.assertTrue(result['schema'])
        self.assertIn('unit_scale_dimension',{e['code'] for e in result['issues']})
    def test_all_quantities_checked_even_with_one_correct_match(self):
        r=valid('signed');r['quantities'].append(q('extra','7'))
        result=self.check(r);self.assertTrue(result['quantity_0']);self.assertFalse(result['mechanical_pass'])
    def test_undefined_operand_and_unlinked_literal_calculation_are_not_arithmetic_passes(self):
        r=valid('scale');r['calculation']['operand_ids'].append('scale_factor')
        self.assertIn('undefined_operand',{e['code'] for e in self.check(r,'scale')['issues']})
        r=valid('margin');r['calculation']['expression']='(240-180)/240*100'
        result=self.check(r,'margin');self.assertTrue(result['arithmetic_25_percent'])
        self.assertFalse(result['mechanical_pass']);self.assertIn('unlinked_calculation',{e['code'] for e in result['issues']})
    def test_duplicate_ids_and_unused_declared_operands_fail(self):
        r=valid('signed');r['quantities']*=2
        self.assertIn('duplicate_quantity_id',{e['code'] for e in self.check(r)['issues']})
        r=valid('scale');r['calculation']['operand_ids'].append('converted')
        self.assertIn('operand_expression_mismatch',{e['code'] for e in self.check(r,'scale')['issues']})
    def test_arithmetic_wrong_result_wrong_unit_and_unrequested_total_fail(self):
        r=valid('margin');r['calculation']['result']='24'
        self.assertIn('arithmetic_mismatch',{e['code'] for e in self.check(r,'margin')['issues']})
        r=valid('scale');r['calculation']['unit']='USD billion'
        self.assertFalse(self.check(r,'scale')['mechanical_pass'])
        r=valid('comparison');r['calculation']={'operand_ids':['operations','investing','financing'],'expression':'operations+investing+financing','result':'19','unit':'USD million'}
        self.assertIn('unrequested_calculation',{e['code'] for e in self.check(r,'comparison')['issues']})
    def test_capacity_abstention_cannot_assert_a_solution_in_claim_or_answer(self):
        self.assertIn('abstention_conflict',{e['code'] for e in self.check(original('capacity'),'capacity')['issues']})
        r=valid('capacity');r['answer']='The quick ratio can be calculated.'
        self.assertFalse(self.check(r,'capacity')['mechanical_pass'])
    def test_json_duplicates_nonfinite_and_extra_fields_fail_without_repair(self):
        for raw in ['{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}']:
            with self.assertRaises(ValueError):strict_json(raw)
        r=valid('missing');r['repair_note']='secret'
        with self.assertRaises(ValueError):validate_schema(r)
        for field in ['unit','id','scale','value']:
            r=valid('signed');r['quantities'][0][field]=[]
            self.assertFalse(self.check(r)['mechanical_pass'])
    def test_year_scale_and_literal_citation_are_independent_checks(self):
        r=valid('signed');r['quantities'][0].update(value='-12500',scale='thousand')
        self.assertTrue(self.check(r)['mechanical_pass'])
        r['quantities'][0]['fiscal_year']='2030';self.assertFalse(self.check(r)['mechanical_pass'])
        r=valid('signed');r['quantities'][0]['source']['page_id']=1
        self.assertFalse(self.check(r)['mechanical_pass'])


class EffectiveRuntimeTests(unittest.TestCase):
    def test_explicit_off_is_verified_and_auto_enabled_is_rejected(self):
        self.assertEqual(require_settings(OFF_LOG)['flash_attention_effective'],'disabled')
        self.assertEqual(observe_settings(AUTO_LOG)['flash_attention_effective'],'enabled')
        with self.assertRaisesRegex(ValueError,'Effective backend'):require_settings(AUTO_LOG)
    def test_partial_offload_missing_log_and_wrong_context_fail(self):
        for log in ['',OFF_LOG.replace('37/37','36/37'),OFF_LOG.replace('n_ctx = 6144','n_ctx = 8192'),OFF_LOG.replace('K (f16)','K (q8_0)')]:
            with self.assertRaises(ValueError):require_settings(log)
    def test_v1_setup_is_rejected_without_touching_its_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);setup=root/'setup.json';ledger=root/'synthetic_campaign.json'
            write_json(setup,{'version':'bounded-answer-preparation-v1'});ledger.write_text('original')
            with patch('finocr_answer.feasibility.subprocess.Popen') as backend:
                with self.assertRaisesRegex(ValueError,'Preserve the v1'):run(setup,root/'new',root)
                backend.assert_not_called();self.assertEqual(ledger.read_text(),'original');self.assertFalse((root/'new').exists())


class AuditAndBudgetTests(unittest.TestCase):
    def setUp(self):
        self.guard=patch("finocr_answer.followup.require_inference_authorized");self.guard.start();self.addCleanup(self.guard.stop)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run_dir,self.setup,self.campaign=legacy_fixture(self.root)
    def tearDown(self):self.tmp.cleanup()
    def test_offline_audit_reconciles_hashes_and_changes_no_original_bytes(self):
        before=snapshot(self.run_dir,self.setup,self.campaign)
        with patch('subprocess.Popen',side_effect=AssertionError('No model/process')):
            r=audit_to_directory(self.run_dir,self.setup,self.campaign,self.root/'audit')
        self.assertEqual(r['strict_mechanical_pass_count'],1);self.assertEqual(r['additional_inference_requests'],0)
        self.assertFalse(r['intended_flash_attention_reproduced']);self.assertEqual(before,snapshot(self.run_dir,self.setup,self.campaign))
    def test_offline_audit_refuses_overwrite_and_nested_output(self):
        out=self.root/'audit';audit_to_directory(self.run_dir,self.setup,self.campaign,out)
        with self.assertRaises(FileExistsError):audit_to_directory(self.run_dir,self.setup,self.campaign,out)
        with self.assertRaises(ValueError):audit_to_directory(self.run_dir,self.setup,self.campaign,self.run_dir/'audit')
    def test_tampered_raw_output_parsed_output_and_ledger_are_rejected(self):
        raw=self.run_dir/'signed/raw-response.sse';old=raw.read_bytes();raw.write_bytes(old+b' ')
        with self.assertRaisesRegex(ValueError,'Raw response hash'):audit_original(self.run_dir,self.setup,self.campaign)
        raw.write_bytes(old);parsed=self.run_dir/'signed/parsed.json';parsed.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Parsed response'):audit_original(self.run_dir,self.setup,self.campaign)
    def test_resource_summary_mismatch_is_rejected(self):
        p=self.run_dir/'run_manifest.json';m=strict_json(p.read_text());m['memory']['device_wide_sampled_peak_used_mib']=1;write_json(p,m)
        with self.assertRaisesRegex(ValueError,'resource'):audit_original(self.run_dir,self.setup,self.campaign)
    def prepare(self):
        with patch('finocr_answer.followup.verify_assets'),patch('finocr_answer.followup.runtime',return_value={}):
            return prepare_followup(self.setup,self.campaign,self.run_dir,Path(__file__).resolve().parents[1])
    def test_followup_has_new_six_request_ticket_preserves_model_and_exhausted_ledger(self):
        before=snapshot(self.run_dir,self.setup,self.campaign);r=self.prepare();new_path=Path(r['setup']);new=strict_json(new_path.read_text())
        self.assertEqual(new['budget'],BUDGET);self.assertEqual(new['version'],VERSION);self.assertEqual(new['execution'],EXECUTION)
        self.assertEqual(new['model'],strict_json(self.setup.read_text())['model']);self.assertEqual(r['additional_inference_budget'],6)
        self.assertEqual(before,snapshot(self.run_dir,self.setup,self.campaign));self.assertFalse((new_path.parent/'synthetic_campaign.json').exists())
        validate_followup_setup(new,new_path,new_path.parent/'run')
        with self.assertRaises(FileExistsError):self.prepare()
    def test_changed_budget_copied_ticket_and_original_mutation_fail(self):
        p=Path(self.prepare()['setup']);s=strict_json(p.read_text());s['budget']['additional_requests']=7
        with self.assertRaises(ValueError):validate_followup_setup(s,p,p.parent/'run')
        s=strict_json(p.read_text())
        with self.assertRaises(ValueError):validate_followup_setup(s,self.root/'copied.json',p.parent/'run')
        with self.assertRaises(ValueError):validate_followup_setup(s,p,self.root/'different-run')
        s['cache_root']=str(self.setup.parent/'cache')
        with self.assertRaisesRegex(ValueError,'isolated v2 cache'):validate_followup_setup(s,p,p.parent/'run')
        s=strict_json(p.read_text())
        self.campaign.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Original'):require_lineage(s)
    def test_no_new_ticket_if_runtime_or_model_bytes_changed(self):
        with patch('finocr_answer.followup.runtime',return_value={'changed':True}):
            with self.assertRaisesRegex(ValueError,'runtime'):prepare_followup(self.setup,self.campaign,self.run_dir,self.root)
        model=Path(strict_json(self.setup.read_text())['model']['path']);model.write_bytes(b'changed')
        with patch('finocr_answer.followup.verify_assets'),patch('finocr_answer.followup.runtime',return_value={}):
            with self.assertRaisesRegex(ValueError,'Model/backend'):prepare_followup(self.setup,self.campaign,self.run_dir,self.root)
        self.assertFalse(followup_root(self.setup.parent).exists())


class BoundedRunnerTests(unittest.TestCase):
    def exercise(self,mode):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            stack.enter_context(patch("finocr_answer.followup.require_inference_authorized"))
            stack.enter_context(patch("finocr_answer.feasibility.require_inference_authorized"))
            root=Path(tmp);run_dir,old_setup,old_campaign=legacy_fixture(root)
            with patch('finocr_answer.followup.verify_assets'),patch('finocr_answer.followup.runtime',return_value={}):
                prepared=prepare_followup(old_setup,old_campaign,run_dir,Path(__file__).resolve().parents[1])
            setup=Path(prepared['setup']);out=setup.parent/'run';before=snapshot(run_dir,old_setup,old_campaign)
            current={};calls=[];process=Mock();process.poll.return_value=None
            class Tokenizer:
                def decode(self,ids,**kwargs):return ''
            def fake_pack(case,tokenizer):
                name=case['task_id'].split(':')[1];r=run_dir/name
                prompt=(r/'prompt.txt').read_text();tokens=strict_json((r/'request.json').read_text())['prompt']
                if mode=='prompt' and name=='capacity':prompt+=' changed'
                packed={'prompt':prompt,'token_ids':tokens,'retained':[{'page_id':i,'retained_token_ids':[]} for i in range(5)]}
                return [{'case':name}],packed
            def post(url,value):
                if url.endswith('/apply-template'):
                    name=value['messages'][0]['case'];current['case']=name
                    prompt=(run_dir/name/'prompt.txt').read_text()
                    return {'prompt':prompt+' changed' if mode=='prompt' and name=='capacity' else prompt}
                return {'tokens':strict_json((run_dir/current['case']/'request.json').read_text())['prompt']}
            def start(command,stdout,stderr,**kwargs):
                self.assertEqual(command[command.index('--flash-attn')+1],'off')
                stderr.write((AUTO_LOG if mode=='auto' else OFF_LOG).encode());stderr.flush();return process
            def complete(url,payload,path,process):
                calls.append(payload);value=valid('missing');content=json.dumps(value)
                final={'content':content,'stop':True,'tokens_predicted':120,'stop_type':'eos'}
                path.write_text('data: '+json.dumps(final)+'\n\n');return {'status':'received','wall_seconds':.01}
            stack.enter_context(patch('finocr_answer.feasibility.verify_assets'))
            stack.enter_context(patch('finocr_answer.feasibility.runtime',return_value={}))
            stack.enter_context(patch('platform.system',return_value='Windows'))
            stack.enter_context(patch.dict('sys.modules',{'transformers':SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**k:Tokenizer()))}))
            stack.enter_context(patch('finocr_answer.feasibility.pack',side_effect=fake_pack))
            stack.enter_context(patch('finocr_answer.feasibility.post',side_effect=post))
            stack.enter_context(patch('finocr_answer.feasibility.subprocess.Popen',side_effect=start))
            stack.enter_context(patch('finocr_answer.feasibility.Monitor',return_value=Mock(summary=lambda:{'sample_count':1,'device_wide_sampled_peak_used_mib':4000,'measurement_errors':[]})))
            opener=Mock();opener.open.side_effect=lambda *a,**k:__import__('io').BytesIO(b'{"status":"ok"}')
            stack.enter_context(patch('urllib.request.build_opener',return_value=opener))
            stack.enter_context(patch('finocr_answer.feasibility.stream_completion',side_effect=complete))
            result=run(setup,out,Path(__file__).resolve().parents[1])
            self.assertEqual(before,snapshot(run_dir,old_setup,old_campaign));self.assertTrue(result['original_artifacts_unchanged'])
            expected=6 if mode=='normal' else 0
            self.assertEqual(len(calls),expected);self.assertEqual(result['attempted'],expected)
            self.assertEqual(strict_json((setup.parent/'synthetic_campaign.json').read_text())['attempted'],expected)
            if mode=='normal':
                with self.assertRaises((ValueError,FileExistsError)):run(setup,out,root)
                self.assertEqual(len(calls),6)
            else:self.assertEqual(result['status'],'stopped')
    def test_followup_six_calls_keep_originals_and_cannot_restart(self):self.exercise('normal')
    def test_auto_flash_stops_before_first_completion(self):self.exercise('auto')
    def test_last_prompt_control_failure_stops_before_any_completion(self):self.exercise('prompt')


if __name__=='__main__':unittest.main()
