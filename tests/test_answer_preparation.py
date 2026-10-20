"""No model inference: typed scoring, leakage guards, budgets and failure retention."""
import copy
import hashlib
import io
import json
import tempfile
import threading
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from pypdf import PdfWriter
from finocr_answer.historical_contract_v2 import messages, validate_schema, digest, canonical
from finocr_answer.evaluator import arithmetic, decimal_string, quantity_check, citation_check, check_private_key
from finocr_answer.synthetic import historical_cases_v2 as cases, pack_historical_v2 as pack
from finocr_answer.feasibility import parse_stream, stream_completion, stop_process, functional_checks, run
from finocr_answer.setup import download, acquire, identity, sha


class Tokenizer:
    """Reversible four-character test tokenizer, never a model tokenizer."""
    def __init__(self): self.values={}; self.inverse={}
    def encode(self,text,add_special_tokens=False):
        result=[]
        for i in range(0,len(text),4):
            part=text[i:i+4]
            if part not in self.values:
                k=len(self.values); self.values[part]=k; self.inverse[k]=part
            result.append(self.values[part])
        return result
    def decode(self,tokens,**kwargs): return ''.join(self.inverse[t] for t in tokens)
    def apply_chat_template(self,turns,**kwargs): return ''.join(f"<{t['role']}>"+t['content']+f"</{t['role']}>" for t in turns)+'<assistant>'


def response():
    return {'status':'insufficient_evidence','answer':'insufficient_evidence','claims':[],'quantities':[],
            'calculation':None,'missing_information':['Current liabilities']}


def sse(content,**overrides):
    return ('data: '+json.dumps({'content':content[:7],'stop':False})+'\n\n'+'data: '+json.dumps(
        {'content':content[7:],'stop':True,'tokens_predicted':120,'stop_type':'eos',**overrides})+'\n\n').encode()


class AnswerChecks(unittest.TestCase):
    def setUp(self):
        self.expected={'value':'-12.5','unit':'amount','currency':'USD','scale':'million','fiscal_year':'2031','quantum':'0.1'}
    def test_signed_parentheses_grouping_unicode_and_bad_formats(self):
        for value in ('(1,250.00)','−1250.00','-1250.00'): self.assertEqual(decimal_string(value),Decimal('-1250.00'))
        for value in ('(−12)','1,25','$12','1e3','nan','1 250'):
            with self.assertRaises(ValueError): decimal_string(value)
    def test_scale_equivalence_without_discarding_units_year_sign(self):
        actual={**self.expected,'value':'-12500','scale':'thousand'}
        self.assertTrue(quantity_check(actual,self.expected)['pass'])
        for field,value in [('unit','percent'),('currency','EUR'),('fiscal_year','2030'),('value','12500'),('scale','unit')]:
            self.assertFalse(quantity_check({**actual,field:value},self.expected)['pass'])
    def test_round_half_up_boundary_and_exact_zero(self):
        expected={**self.expected,'value':'4.2','unit':'percent','scale':'unit'}
        for v,good in [('4.15',True),('4.249',True),('4.25',False),('4.149',False)]:
            self.assertEqual(quantity_check({**expected,'value':v},expected)['pass'],good)
        expected.update(value='0',exact_zero=True)
        self.assertFalse(quantity_check({**expected,'value':'0.001'},expected)['pass'])
    def test_restricted_decimal_arithmetic_is_exact_and_rejects_code(self):
        self.assertEqual(arithmetic('(sales-cost)/sales*100',{'sales':Decimal(240),'cost':Decimal(180)}),Decimal(25))
        self.assertEqual(arithmetic('0.1+0.2',{}),Decimal('0.3'))
        for value in ['__import__("os")','a.real','2**3','a[0]','1/0','True','a//2','[a for a in b]']:
            with self.assertRaises((ValueError,SyntaxError)): arithmetic(value,{'a':Decimal(3)})
    def test_citations_are_zero_based_literal_and_only_whitespace_normalized(self):
        pages={0:'Cash\n  was (12.5) USD million.'}
        self.assertTrue(citation_check({'page_id':0,'span':'Cash was (12.5)'},pages))
        for pointer in [{'page_id':1,'span':'Cash'},{'page_id':False,'span':'Cash'},{'page_id':0,'span':'cash'},{'page_id':0,'span':''},{'page_id':0,'span':'12.5 USD'}]:
            self.assertFalse(citation_check(pointer,pages))
    def test_schema_rejects_missing_extra_negative_pages_and_boolean_ids(self):
        good=response(); validate_schema(good)
        for bad in [{**good,'answers':['secret']},{k:v for k,v in good.items() if k!='claims'}, {**good,'status':'maybe'}]:
            with self.assertRaises(ValueError): validate_schema(bad)
        for number in (-1,False):
            bad={**good,'claims':[{'text':'x','support':[{'page_id':number,'span':'x'}]}]}
            with self.assertRaises(ValueError): validate_schema(bad)
    def test_model_input_allowlist_rejects_all_labels_and_benchmark_inputs(self):
        fixture=cases()[0]; before=copy.deepcopy(fixture); messages(fixture); self.assertEqual(before,fixture)
        for key in ['answers','justification','evidence_pages','question_type','expanded_query','scores']:
            with self.assertRaises(ValueError): messages({**fixture,key:'secret'})
        with self.assertRaises(ValueError): messages({**fixture,'task_id':'financebench:financebench_id_00000'})
        with self.assertRaises(ValueError): messages({**fixture,'pages':[{**fixture['pages'][0],'confidence':.9}]+fixture['pages'][1:]})
    def test_six_cases_only_no_financebench_and_deterministic_hashes(self):
        fixtures=cases(); self.assertEqual(len(fixtures),6); self.assertEqual(digest(fixtures),digest(cases()))
        self.assertNotIn('financebench',canonical(fixtures).decode().lower())
        self.assertNotIn('answers',canonical(fixtures).decode())
    def test_prefix_packing_full_five_candidates_and_exact_maximum_context(self):
        tokenizer=Tokenizer()
        for case in cases():
            before=copy.deepcopy(case); turns,record=pack(case,tokenizer)
            self.assertEqual(before,case); self.assertEqual([p['page_id'] for p in record['retained']],list(range(5)))
            self.assertLessEqual(record['evidence_tokens'],4096); self.assertLessEqual(record['overhead_tokens'],1024)
            self.assertTrue(all(p['retained_interval'][1]<=800 for p in record['retained']))
            if case['task_id']=='synthetic:capacity':
                self.assertEqual(record['input_tokens'],5120); self.assertEqual(record['evidence_tokens'],4096)
                self.assertTrue(all(p['truncated'] for p in record['retained']))
    def test_raw_stream_join_preserves_text_and_truncation_metadata(self):
        raw=sse(json.dumps(response()),stop_type='limit')
        text,final=parse_stream(raw); self.assertEqual(json.loads(text),response()); self.assertEqual(final['stop_type'],'limit')
        with self.assertRaises(ValueError): parse_stream(b'data: {"content":"partial"}\n\n')
    def test_missing_case_does_not_demand_fabricated_citations(self):
        checks=functional_checks(response(),'missing',{0:'Current liabilities were not supplied.'})
        self.assertTrue(checks['schema']); self.assertTrue(checks['expected_status']); self.assertTrue(checks['explicit_missing_facts'])
    def test_deadline_stops_owned_server_and_keeps_partial_sse(self):
        with tempfile.TemporaryDirectory() as temp:
            process=Mock(); process.poll.return_value=None
            release=threading.Event()
            class BlockingResponse:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def __iter__(self):
                    yield b'data: {"content":"partial"}\n\n'; release.wait(2)
            process.terminate.side_effect=release.set
            opener=Mock(); opener.open.return_value=BlockingResponse()
            path=Path(temp)/'raw.sse'
            with patch('urllib.request.build_opener',return_value=opener):
                result=stream_completion('http://127.0.0.1:1/completion',{},path,process,deadline=.03)
            self.assertEqual(result['status'],'deadline'); process.terminate.assert_called_once()
            self.assertIn(b'partial',path.read_bytes())
    def test_failed_download_keeps_partial_and_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model'; path.write_bytes(b'old')
            with self.assertRaises(ValueError): download('https://example.invalid',path,'wrong')
            self.assertEqual(path.read_bytes(),b'old')
            path.unlink()
            with patch('urllib.request.urlopen',return_value=io.BytesIO(b'bad')):
                with self.assertRaises(ValueError): download('https://example.invalid',path,'wrong')
            self.assertEqual(path.with_name('model.partial').read_bytes(),b'bad'); self.assertFalse(path.exists())
    def test_memory_accounting_records_client_server_system_and_device_scopes(self):
        from types import SimpleNamespace
        from finocr_answer.feasibility import Monitor
        with tempfile.TemporaryDirectory() as temp:
            fake=SimpleNamespace(Process=lambda pid:SimpleNamespace(memory_info=lambda:SimpleNamespace(rss=100 if pid==123 else 20,peak_wset=110)),
                                 virtual_memory=lambda:SimpleNamespace(total=1600,available=900))
            with patch.dict('sys.modules',{'psutil':fake}),patch('subprocess.check_output',return_value='0, NVIDIA GeForce RTX 3070 Ti, 537.70, 8192, 4000\n'):
                monitor=Monitor(123,Path(temp)/'memory.jsonl')
                monitor.done.wait=lambda interval:monitor.done.set()
                monitor.run();result=monitor.summary()
            self.assertEqual(result['sample_count'],1)
            self.assertEqual(result['sampled_peak_sum_rss_bytes'],120)
            self.assertEqual(result['minimum_system_available_bytes'],900)
            self.assertEqual(result['sampled_peak_system_used_bytes'],700)
            self.assertEqual(result['device_wide_sampled_peak_used_mib'],4000)
            self.assertEqual(result['measurement_errors'],[])

    def test_setup_zip_rejects_traversal_before_writing_outside_root(self):
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'assets'; (root/'downloads').mkdir(parents=True)
            with zipfile.ZipFile(root/'downloads/backend.zip','w') as z:z.writestr('../outside','bad')
            lock={'model_files':[],'backend_url':'https://example.invalid','backend_zip_sha256':sha(root/'downloads/backend.zip')}
            with self.assertRaisesRegex(ValueError,'Unsafe'): acquire(lock,root)
            self.assertFalse((root/'outside').exists())


class PrivateKeyChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        w=PdfWriter(); w.add_blank_page(width=100,height=100)
        with (self.root/'source.pdf').open('wb') as f:w.write(f)
        self.tasks=[{'task_id':f't{i}','doc_id':'d','answers':['ref'],'evidence_pages':[0]} for i in range(24)]
        self.task_path=self.root/'tasks.jsonl'; self.task_path.write_text('\n'.join(json.dumps(t) for t in self.tasks))
        self.key={'tasks_sha256':sha(self.task_path),'sources':[{'filename':'source.pdf','doc_id':'d','sha256':sha(self.root/'source.pdf'),'page_count':1}],
                  'items':[{**t,'upstream_answers':t['answers'],'upstream_evidence_pages':t['evidence_pages'],'source_review':'reviewed','support_requirements':['literal support'],
                            'adjudication_status':'ready'} for t in self.tasks]}
        self.path=self.root/'rubric.json'
    def tearDown(self):self.temp.cleanup()
    def audit(self,**kwargs):
        self.path.write_text(json.dumps(self.key)); return check_private_key(self.path,self.root,self.task_path,**kwargs)
    def test_complete_source_audit_has_no_generation_and_requires_signoff_to_freeze(self):
        result=self.audit(); self.assertEqual(result['tasks'],24); self.assertFalse(result['generation_executed'])
        with self.assertRaisesRegex(ValueError,'blocked'):self.audit(freeze=True)
    def test_unresolved_reference_issue_blocks_even_signed_key(self):
        self.key['reviewer_signoff']={'reviewer':'fixture','decisions_sha256':'a'*64}
        self.key['items'][0]['adjudication_status']='hold'
        self.assertEqual(self.audit()['held_items'],['t0'])
        with self.assertRaises(ValueError):self.audit(freeze=True)
    def test_prospective_unscorable_decision_needs_reason_and_stays_in_24(self):
        self.key['items'][0]['adjudication_status']='unscorable'
        with self.assertRaisesRegex(ValueError,'resolution'):self.audit()
        self.key['items'][0]['resolution']='Ambiguous reference; decided before predictions.'
        result=self.audit()
        self.assertEqual(result['unscorable_items'],['t0']);self.assertEqual(result['tasks'],24)

    def test_original_label_and_task_file_mutations_fail(self):
        self.key['items'][0]['upstream_answers']=['changed']
        with self.assertRaisesRegex(ValueError,'labels'): self.audit()
        self.task_path.write_text('changed')
        with self.assertRaisesRegex(ValueError,'checksum'):self.audit()
    def test_changed_source_and_missing_cohort_item_fail(self):
        self.key['items'].pop()
        with self.assertRaisesRegex(ValueError,'24'):self.audit()
        self.key['items'].append({**self.key['items'][0],'task_id':'t23'})
        (self.root/'source.pdf').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):self.audit()


class RunnerChecks(unittest.TestCase):
    def test_runner_is_synthetic_only_charges_six_retains_alias_free_provenance_and_refuses_repeat(self):
        from types import SimpleNamespace
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stack.enter_context(patch("finocr_answer.feasibility.require_inference_authorized"))
            root=Path(temp); (root/'official').mkdir(); model=root/'model.gguf';model.write_bytes(b'fixture')
            exe=root/'server.exe';exe.write_bytes(b'fixture');setup_path=root/'setup.json'
            setup={'version':'bounded-answer-preparation-v2','campaign_root':str(root),'cache_root':str(root/'cache'),'execution':{},'budget':{},'control_prompts':{c['task_id'].split(':')[1]:{'prompt_sha256':hashlib.sha256(pack(c,Tokenizer())[1]['prompt'].encode()).hexdigest(),'token_ids_sha256':'fixture'} for c in cases()},'lineage':{},'asset_root':str(root),'lock':{},'model':identity(model),'server':identity(exe),
                   'runtime':{},'source_sha256':'fixture','instruction_sha256':'prompt','schema_sha256':'schema'}
            tokenizer=Tokenizer()
            for c in cases():
                packed=pack(c,tokenizer)[1];setup['control_prompts'][c['task_id'].split(':')[1]]={'prompt_sha256':hashlib.sha256(packed['prompt'].encode()).hexdigest(),'token_ids_sha256':digest(packed['token_ids'])}
            setup_path.write_text(json.dumps(setup)); process=Mock();process.poll.return_value=None
            def start(command,stdout,stderr,**kwargs):
                self.assertEqual(command[command.index('--flash-attn')+1],'off')
                stderr.write(b'offloaded 37/37 layers to GPU; Vulkan0: RTX 3070 Ti\nflash_attn = disabled\nn_ctx = 6144\nn_ctx_per_seq = 6144\nn_seq_max = 1\nn_batch = 512\nn_ubatch = 128\nK (f16): 432, V (f16):432\n');stderr.flush();return process
            def metadata(url,value):
                if url.endswith('/apply-template'):return {'prompt':tokenizer.apply_chat_template(value['messages'])}
                if url.endswith('/tokenize'):return {'tokens':tokenizer.encode(value['content'])}
                raise AssertionError('Unexpected endpoint')
            calls=[]
            def complete(url,payload,path,process):
                calls.append(payload); path.write_bytes(sse(json.dumps(response())))
                return {'status':'received','wall_seconds':.01}
            stack.enter_context(patch('finocr_answer.followup.validate_followup_setup'))
            stack.enter_context(patch('finocr_answer.followup.require_lineage'))
            stack.enter_context(patch('finocr_answer.feasibility.verify_assets'))
            stack.enter_context(patch('finocr_answer.feasibility.runtime',return_value={}))
            stack.enter_context(patch('finocr_answer.feasibility.source_identity',return_value='fixture'))
            stack.enter_context(patch('platform.system',return_value='Windows'))
            stack.enter_context(patch.dict('sys.modules',{'transformers':SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**k:tokenizer))}))
            stack.enter_context(patch('finocr_answer.feasibility.subprocess.Popen',side_effect=start))
            stack.enter_context(patch('finocr_answer.feasibility.Monitor',return_value=Mock(summary=lambda:{'fixture':True})))
            opener=Mock(); opener.open.side_effect=lambda *a,**k:io.BytesIO(b'{"status":"ok"}')
            stack.enter_context(patch('urllib.request.build_opener',return_value=opener))
            stack.enter_context(patch('finocr_answer.feasibility.post',side_effect=metadata))
            stack.enter_context(patch('finocr_answer.feasibility.stream_completion',side_effect=complete))
            result=run(setup_path,root/'run',root)
            self.assertEqual(len(calls),6);self.assertEqual(result['attempted'],6)
            self.assertEqual(result['primary_requests'],0);self.assertFalse(result['benchmark_generation_enabled'])
            self.assertEqual(json.loads((root/'synthetic_campaign.json').read_text())['attempted'],6)
            self.assertTrue((root/'run/capacity/raw-response.sse').exists())
            self.assertTrue(all(p['n_predict']==1024 and p['cache_prompt'] is False for p in calls))
            self.assertEqual(len(calls[-1]['prompt']),5120);self.assertFalse(result['automated_checks_pass'])
            with self.assertRaises(FileExistsError):run(setup_path,root/'different-run',root)
            self.assertEqual(len(calls),6)
    def test_source_identity_change_stops_before_backend_or_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); model=root/'model';model.write_bytes(b'model');exe=root/'exe';exe.write_bytes(b'exe')
            s=root/'setup.json';s.write_text(json.dumps({'version':'bounded-answer-preparation-v2','asset_root':str(root),'lock':{},'model':identity(model),'server':identity(exe),'runtime':{},'source_sha256':'before'}))
            with patch('finocr_answer.feasibility.require_inference_authorized'),patch('finocr_answer.followup.validate_followup_setup'),patch('finocr_answer.feasibility.verify_assets'),patch('finocr_answer.feasibility.source_identity',return_value='changed'),patch('finocr_answer.feasibility.subprocess.Popen') as backend:
                with self.assertRaisesRegex(ValueError,'Code/runtime'):run(s,root/'output',root)
                backend.assert_not_called();self.assertFalse((root/'output').exists())


if __name__=='__main__':unittest.main()
