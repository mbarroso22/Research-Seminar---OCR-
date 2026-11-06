"""Source-only fixtures, mocked OCR/encoder calls; no experimental inference."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines import larger_cohort as cohort, larger_hybrid as pipeline
from finocr.pipelines.larger_spec import SPEC
from finocr.pipelines.native_baseline import run_native_baseline, load_evidence_labels
from finocr.pipelines.report_rendering import file_identity, render_full_reports
from finocr.retrieval.semantic import policy_record as original_policy
import test_full_ocr as fixtures
from test_hybrid_retrieval import FakeEncoder, FakeMemory


class LargerStudyTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.FullOcrTests();self.fx.setUp()
        self.freeze=self.fx.root/'frozen';self.freeze.mkdir()
        self.output=self.fx.root/'larger';self.controls=self.fx.root/'controls'
        self.root=self.fx.root/'code'
        queries=read_jsonl(self.fx.native/'retrieval_queries.jsonl')
        write_jsonl(self.freeze/'retrieval-queries.jsonl',queries)
        write_jsonl(self.freeze/'scorer-tasks.jsonl',self.fx.labels)
        docs=self.fx.docs
        for i,d in enumerate(docs):d['metadata']['company']='Company'+str(i)
        write_jsonl(self.fx.documents,docs)
        write_jsonl(self.freeze/'documents.jsonl',docs)
        proposal={'totals':{'companies':2,'documents':2,'pages':9,'questions':3},'documents':[
            {'doc_id':d['doc_id'],'company':d['metadata']['company'],'page_count':d['page_count'],
             'pdf_identity':file_identity(d['pdf_path'])} for d in docs]}
        write_json(self.freeze/'cohort-proposal.json',proposal)
        write_json(self.freeze/'exploratory-design.json',{'fixture':'no real labels exposed to retrieval'})
        self.specpatch=patch.dict(SPEC,{'totals':proposal['totals'],'ocr_device':'cpu',
            'ocr_model_manifest_sha256':file_identity(self.fx.models/'model_manifest.json')['sha256'],
            'anchors':{name:file_identity(self.freeze/name) for name in ('cohort-proposal.json','retrieval-queries.jsonl','exploratory-design.json')}})
        self.specpatch.start();self.addCleanup(self.specpatch.stop)
        write_json(self.freeze/'cohort-freeze.json',{'schema_version':1,'status':'frozen','experiment':SPEC['experiment'],
            'experimental_group':SPEC['group'],'totals':SPEC['totals'],'policy':cohort.study_policy(),
            'artifacts':{p.name:file_identity(p) for p in self.freeze.iterdir()}})
        self.fx.native=self.fx.root/'new-native'
        run_native_baseline(self.fx.documents,self.freeze/'retrieval-queries.jsonl',self.fx.native,
                            repository_root=self.root,experimental_group=SPEC['group'],skip_evaluation=True)
        self.fx.render=self.fx.root/'new-render'
        def fake_render(command,**kwargs):
            Path(command[-1]).with_suffix('.png').write_bytes(fixtures.fixture_png())
            return subprocess.CompletedProcess(command,0,'','')
        with patch('finocr.pipelines.report_rendering.renderer_identity',return_value={'fixture':True}), \
             patch('finocr.pipelines.report_rendering.code_provenance',return_value={'fixture':True}), \
             patch('finocr.pipelines.report_rendering.subprocess.run',side_effect=fake_render):
            render_full_reports(self.fx.documents,self.fx.render,renderer_path='fixture',native_dir=self.fx.native,repository_root=self.root)
        self.fx.run_ocr()
        FakeEncoder.seen=[];FakeEncoder.overflow=False;FakeEncoder.fail=False
        self.addCleanup(self.fx.tearDown)

    def bind(self):
        return cohort.bind_controls(self.freeze,self.fx.native,self.fx.ocr,self.controls,self.root)

    def compare(self,**kwargs):
        with patch.object(pipeline,'BgeOnnxEncoder',FakeEncoder),patch.object(pipeline,'verify_model',return_value={}),patch.object(pipeline,'MemorySample',FakeMemory):
            return pipeline.compare_larger(self.freeze,self.fx.native,self.controls,self.fx.ocr,
                self.freeze/'scorer-tasks.jsonl',self.fx.models,self.output,repository_root=self.root,**kwargs)

    def test_control_preparation_never_parses_scorer_labels_or_encodes(self):
        with patch.object(pipeline,'load_evidence_labels',side_effect=AssertionError('no labels')):
            result=self.bind()
        self.assertEqual(result['status'],'controls_prepared_no_encoder_no_labels')
        self.assertFalse(FakeEncoder.seen)
        self.assertFalse((self.controls/'comparison_metrics.json').exists())

    def test_check_only_replays_both_controls_without_labels_or_encoder(self):
        self.bind()
        with patch.object(pipeline,'load_evidence_labels',side_effect=AssertionError('no labels')):
            result=self.compare(check_only=True)
        self.assertEqual(result['status'],'inputs_verified_no_encoder')
        self.assertEqual(result['expansion_control_reproduced'],{'native':True,'ocr':True})
        self.assertIsNone(result['promotion_gate']);self.assertFalse(FakeEncoder.seen)

    def test_full_run_has_six_rankings_before_labels_and_no_generation_fields(self):
        self.bind()
        before={p:p.read_bytes() for p in self.fx.root.rglob('*') if p.is_file()}
        def labels(path):
            for c in pipeline.CONDITIONS:
                for m in pipeline.METHODS:self.assertTrue((self.output/f'{c}_{m}_predictions.jsonl').exists())
            return load_evidence_labels(path)
        with patch.object(pipeline,'load_evidence_labels',side_effect=labels):result=self.compare()
        self.assertEqual(result['status'],'complete');self.assertIsNone(result['promotion_gate'])
        metrics=read_json(self.output/'comparison_metrics.json')
        self.assertNotIn('development_gate',metrics)
        self.assertIsNone(metrics['promotion_gate'])
        self.assertEqual(metrics['uncertainty']['primary'],'native_vs_ocr.bm25')
        self.assertEqual(metrics['uncertainty']['native_vs_ocr']['hybrid']['question_count'],3)
        self.assertFalse(any('NEVER_LEAK' in s for s in FakeEncoder.seen))
        for p,raw in before.items():self.assertEqual(p.read_bytes(),raw)

    def test_final_validator_rescores_and_replays_saved_vectors_without_encoder(self):
        self.bind();self.compare()
        script=Path(__file__).resolve().parents[1]/'scripts/run_larger_study.py'
        spec=importlib.util.spec_from_file_location('larger_command',script)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        result=module.validate(argparse.Namespace(freeze_dir=self.freeze,output_dir=self.output))
        self.assertEqual(result['status'],'completion_checks_pass')
        self.assertEqual(result['logical_full_rankings'],18)

    def test_changed_raw_ocr_rejected_before_encoder(self):
        self.bind()
        r=read_jsonl(self.fx.ocr/'ocr_pages.jsonl')[0]
        path=(self.fx.ocr/r['record_path']).parent/'raw_ocr_result.json'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'checksum'):self.compare()
        self.assertFalse(FakeEncoder.seen)

    def test_wrong_frozen_policy_rejected_before_controls(self):
        p=self.freeze/'cohort-freeze.json';m=read_json(p);m['policy']['primary_k']=10;write_json(p,m)
        with self.assertRaisesRegex(ValueError,'frozen contract'):self.bind()

    def test_changed_scorer_even_with_rehashed_freeze_breaks_bound_lineage(self):
        self.bind()
        p=self.freeze/'scorer-tasks.jsonl';p.write_bytes(p.read_bytes()+b'\n')
        f=self.freeze/'cohort-freeze.json';m=read_json(f);m['artifacts'][p.name]=file_identity(p);write_json(f,m)
        with self.assertRaisesRegex(ValueError,'control lineage'):self.compare()

    def test_wrong_saved_control_fails_replay_even_after_inventory_rehash(self):
        self.bind();p=self.controls/'native_predictions.jsonl';rows=read_jsonl(p)
        rows[0]['ranked_pages'][0]['score']+=.1;write_jsonl(p,rows)
        mp=self.controls/'run_manifest.json';m=read_json(mp);m['artifacts'][p.name]=file_identity(p);write_json(mp,m)
        with self.assertRaisesRegex(ValueError,'Control ranking failed reproduction'):self.compare()
        self.assertFalse(FakeEncoder.seen)

    def test_original_pilot_guard_still_rejects_larger_cache(self):
        from finocr.pipelines import hybrid_comparison as original
        self.bind()
        with self.assertRaisesRegex(ValueError,'Not the frozen original'):
            original.load_inputs(self.fx.native,self.controls,self.fx.ocr,self.freeze/'scorer-tasks.jsonl',{})

    def test_existing_outputs_preserved(self):
        self.bind()
        with self.assertRaisesRegex(ValueError,'Existing output'):self.bind()
        self.output.mkdir();(self.output/'retained').write_text('old')
        with self.assertRaises(FileExistsError):self.compare()
        self.assertEqual((self.output/'retained').read_text(),'old')

    def test_failed_encoder_retains_controls_and_failure_stage(self):
        self.bind();FakeEncoder.fail=True
        with self.assertRaisesRegex(RuntimeError,'fixture encoder'):self.compare()
        m=read_json(self.output/'run_manifest.json')
        self.assertEqual(m['status'],'failed');self.assertEqual(m['stage'],'semantic_encoding')
        self.assertTrue((self.output/'native_bm25_predictions.jsonl').exists())


class ClusterTests(unittest.TestCase):
    def case(self,values):
        return {'per_question':[{'task_id':str(i),'doc_id':doc,'at_k':{'5':{'evidence_recall':value}}}
                                for i,(doc,value) in enumerate(values)]}
    def test_company_clusters_preserve_unequal_question_counts(self):
        docs=[{'doc_id':k,'metadata':{'company':k}} for k in ('a','b')]
        a=self.case([('a',0),('a',0),('b',1)])
        b=self.case([('a',1),('a',1),('b',0)])
        result=pipeline.cluster_delta(a,b,docs)
        self.assertAlmostEqual(result['question_weighted_delta'],1/3)
        self.assertEqual(result['equal_company_delta'],0)
        self.assertEqual(result['question_weighted_ci95'],[-1,1])
        self.assertEqual(result,pipeline.cluster_delta(a,b,docs))
    def test_zero_paired_difference_has_zero_interval(self):
        docs=[{'doc_id':'a','metadata':{'company':'a'}}]
        a=self.case([('a',.5)])
        r=pipeline.cluster_delta(a,a,docs)
        self.assertEqual(r['question_weighted_ci95'],[0,0])
    def test_mismatched_task_and_report_pairs_are_rejected(self):
        docs=[{'doc_id':k,'metadata':{'company':k}} for k in ('a','b')]
        with self.assertRaisesRegex(ValueError,'report pairing'):
            pipeline.cluster_delta(self.case([('a',0)]),self.case([('b',1)]),docs)
    def test_original_encoder_policy_and_gate_are_not_overwritten(self):
        before=original_policy();p=cohort.study_policy()
        self.assertEqual(original_policy(),before)
        self.assertIsNone(p['gate'])
        self.assertEqual(p['encoder_settings_original_policy_sha256'],before['sha256'])
        self.assertEqual(p['totals'],SPEC['totals'])


class FreezeTests(unittest.TestCase):
    def setUp(self):
        from test_native_baseline import text_pdf
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.study=self.root/'study';self.study.mkdir()
        self.data=self.root/'data';self.source=self.data/'raw/financebench/data';self.source.mkdir(parents=True)
        self.pdfs=self.data/'raw/financebench/pdfs';self.pdfs.mkdir(parents=True)
        self.output=self.root/'frozen';self.code=self.root/'code'
        self.metadata=[];self.raw=[];self.docs=[];self.queries=[]
        for i in range(2):
            name=f'FIXTURE{i}_2022_10K';pdf=self.pdfs/(name+'.pdf');text_pdf(pdf,['first','second'])
            self.metadata.append({'doc_name':name,'doc_type':'10k','company':f'Fixture{i}'})
            self.raw.append({'financebench_id':f'q{i}','doc_name':name,'question':'revenue',
                             'answer':'NEVER_LEAK','evidence':[{'evidence_page_num':0,'evidence_text':'NEVER_LEAK'}]})
            self.docs.append({'doc_name':name,'doc_id':'financebench:'+name,'company':f'Fixture{i}',
                              'pdf_basename':pdf.name,'pdf_identity':file_identity(pdf),'page_count':2,'question_count':1})
            self.queries.append({'task_id':f'financebench:q{i}','doc_id':'financebench:'+name,'question':'revenue'})
        duplicate={'doc_name':'UNRELATED_2023_annualreport','doc_type':'annualreport','company':'Other'}
        self.metadata.extend([duplicate,duplicate])
        self.patch=patch.dict(SPEC,{'totals':{'companies':2,'documents':2,'pages':4,'questions':2}})
        self.patch.start();self.addCleanup(self.patch.stop)
        self.refresh()
    def refresh(self):
        write_jsonl(self.source/'financebench_document_information.jsonl',self.metadata)
        write_jsonl(self.source/'financebench_open_source.jsonl',self.raw)
        write_jsonl(self.study/'retrieval-queries.jsonl',self.queries)
        write_json(self.study/'exploratory-design.json',{'fixture':True})
        write_json(self.study/'cohort-proposal.json',{'totals':SPEC['totals'],'documents':self.docs,
            'excluded_companies':SPEC['excluded_companies'],
            'source_files':{p.name:file_identity(p) for p in self.source.iterdir()}})
        SPEC['anchors']={p.name:file_identity(p) for p in self.study.iterdir()}
    def freeze(self):return cohort.freeze(self.study,self.data,self.output,self.code)
    def test_freeze_keeps_all_questions_and_emits_no_answer_or_evidence_text(self):
        self.assertEqual(self.freeze()['status'],'frozen')
        data=read_jsonl(self.output/'scorer-tasks.jsonl')
        self.assertEqual(len(data),2)
        self.assertTrue(all(set(r)=={'task_id','doc_id','question','evidence_pages'} for r in data))
        self.assertFalse(any(b'NEVER_LEAK' in p.read_bytes() for p in self.output.iterdir()))
        cohort.read_freeze(self.output,{})
    def test_changed_pdf_stops_before_freeze_output(self):
        p=self.pdfs/self.docs[0]['pdf_basename'];p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'PDF identity changed'):self.freeze()
        self.assertFalse(self.output.exists())
    def test_cross_report_annotation_stops_without_silently_dropping_question(self):
        self.raw[0]['evidence'][0]['evidence_doc_name']='OTHER';self.refresh()
        with self.assertRaisesRegex(ValueError,'Cross-report annotation'):self.freeze()
        self.assertFalse(self.output.exists())
    def test_out_of_range_label_stops_before_execution(self):
        self.raw[0]['evidence'][0]['evidence_page_num']=2;self.refresh()
        with self.assertRaisesRegex(ValueError,'Invalid zero-based evidence'):self.freeze()
        self.assertFalse(self.output.exists())
    def test_company_wide_membership_cannot_silently_drop_a_question(self):
        self.raw.append({**self.raw[0],'financebench_id':'extra'});self.refresh()
        with self.assertRaisesRegex(ValueError,'Whole-company annual question coverage'):self.freeze()


if __name__=='__main__':unittest.main()
