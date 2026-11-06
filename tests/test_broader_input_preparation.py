"""Offline input/specification checks. GPU and OCR execution are mocked."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

spec=importlib.util.spec_from_file_location('broader_prep',Path(__file__).resolve().parents[1]/'scripts/prepare_broader_inputs.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class BroaderPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.manifest={'status':'complete','run_id':'2ceb1dc5ae404c01b65e7128ea5afb3b','contract':{'runtime':{'packages':{'paddlepaddle-gpu':'3.3.0','paddleocr':'3.3.2','paddlex':'3.3.10','pip':'25.0.1','financial-ocr-research':'0.2.0'}}}}
        self.raw=(json.dumps(self.manifest)+'\n').encode();self.digest=hashlib.sha256(self.raw).hexdigest()
    def tearDown(self):self.temp.cleanup()
    def test_export_finds_archived_windows_paths_and_preserves_archive(self):
        imports=self.root/'imports';imports.mkdir();zpath=imports/'completed.zip'
        with zipfile.ZipFile(zpath,'w') as z:z.writestr('gpu-cache\\run_manifest.json',self.raw)
        before=zpath.read_bytes()
        with patch.object(p,'GPU_MANIFEST',self.digest):r=p.export_runtime(imports,self.root/'pins')
        self.assertEqual(r['status'],'pins_exported');self.assertEqual(zpath.read_bytes(),before)
        pins=(self.root/'pins/gpu-nonframework-exact.txt').read_text()
        self.assertIn('paddleocr==3.3.2',pins);self.assertNotIn('paddlepaddle-gpu==',pins);self.assertNotIn('financial-ocr-research',pins)
        with patch.object(p,'GPU_MANIFEST',self.digest),self.assertRaises(FileExistsError):p.export_runtime(imports,self.root/'pins')
    def test_wrong_reference_does_not_export_replacement_pins(self):
        imports=self.root/'imports';imports.mkdir();(imports/'run_manifest.json').write_bytes(self.raw+b' ')
        with patch.object(p,'GPU_MANIFEST',self.digest),self.assertRaisesRegex(ValueError,'verified completed GPU manifest'):
            p.export_runtime(imports,self.root/'pins')
        self.assertFalse((self.root/'pins').exists())
    def test_runtime_package_mismatch_records_failure_before_paddle_import(self):
        ref=self.root/'reference.json';ref.write_bytes(self.raw);output=self.root/'runtime.json'
        import finocr
        repo=Path(finocr.__file__).resolve().parents[2]
        with patch.object(p,'GPU_MANIFEST',self.digest),patch.object(p.sys,'version_info',(3,12,10)),patch.object(p.metadata,'version',return_value='wrong'):
            with self.assertRaisesRegex(ValueError,'preserved GPU specification'):p.check_runtime(ref,repo,output)
        self.assertEqual(p.load(output)['status'],'failed')
        self.assertTrue(p.load(output)['package_differences'])
    def cohort_fixture(self):
        from finocr.pipelines.ocr_device import device_condition
        from test_native_baseline import text_pdf
        data=self.root/'data';pdfs=data/'raw/financebench/pdfs';sources=data/'raw/financebench/data'
        pdfs.mkdir(parents=True);sources.mkdir(parents=True)
        pdf=pdfs/'FIXTURE_2022_10K.pdf';text_pdf(pdf,['revenue','cash flow'])
        meta={'company':'Fixture','doc_type':'10k','doc_name':'FIXTURE_2022_10K'}
        q={'financebench_id':'fixture_q','doc_name':'FIXTURE_2022_10K','question':'revenue cash flow','answer':'NEVER_LEAK_ANSWER','justification':'NEVER_LEAK_JUSTIFICATION','evidence':[{'doc_name':'FIXTURE_2022_10K','evidence_page_num':0,'evidence_text':'NEVER_LEAK_TEXT'},{'doc_name':'FIXTURE_2022_10K','evidence_page_num':1}]}
        (sources/'financebench_document_information.jsonl').write_text(json.dumps(meta)+'\n');(sources/'financebench_open_source.jsonl').write_text(json.dumps(q)+'\n')
        proposal={'required_source_files':{f.name:p.identity(f) for f in sources.iterdir()},'documents':[{'doc_id':'financebench:FIXTURE_2022_10K','doc_name':'FIXTURE_2022_10K','pdf_basename':pdf.name,'company':'Fixture','fiscal_year':2022,'expected_pages':2,'pdf_sha256':p.identity(pdf)['sha256'],'question_ids':['fixture_q']}],'totals':{'question_bearing_reports':1,'pages':2,'questions':1,'multipage_questions':1},'reserved_company_annual_doc_names':['FIXTURE_2022_10K'],'settings_to_freeze':{'primary_k':5}}
        pp=self.root/'proposal.json';p.save(pp,proposal)
        cfg,pins=device_condition('gpu:0');renderer_data={'version_output':'fixture','binary_identities':{'fixture':True}};reference={'contract':{'configuration':cfg,'package_pins':pins,'render_contract':{'renderer':renderer_data}}}
        renderer_patch=patch('finocr.pipelines.report_rendering.renderer_identity',return_value=renderer_data);renderer_patch.start();self.addCleanup(renderer_patch.stop)
        ref=self.root/'reference.json';p.save(ref,reference)
        models=self.root/'models';models.mkdir();p.save(models/'model_manifest.json',{'fixture':True})
        runtime=self.root/'runtime.json';p.save(runtime,{'status':'setup_complete'})
        renderer=self.root/'renderer';renderer.write_bytes(b'fixture renderer')
        return pp,data,ref,models,runtime,renderer
    def test_freeze_preserves_zero_based_labels_and_excludes_answer_material(self):
        pp,data,ref,models,runtime,renderer=self.cohort_fixture()
        with patch.object(p,'GPU_MANIFEST',p.identity(ref)['sha256']),patch.object(p,'MODEL_MANIFEST',p.identity(models/'model_manifest.json')['sha256']):
            result=p.freeze_cohort(pp,data,self.root,runtime,ref,renderer,models,self.root/'cohort','no_known_prior_content_inspection')
        self.assertEqual(result['status'],'cohort_frozen')
        tasks=(self.root/'cohort/tasks.jsonl').read_text();self.assertNotIn('NEVER_LEAK',tasks)
        self.assertEqual(json.loads(tasks)['evidence_pages'],[0,1])
        query=json.loads((self.root/'cohort/retrieval-queries.jsonl').read_text());self.assertEqual(set(query),{'task_id','doc_id','question'})
    def test_changed_pdf_rejected_before_freeze_outputs(self):
        pp,data,ref,models,runtime,renderer=self.cohort_fixture()
        pdf=next((data/'raw/financebench/pdfs').glob('*.pdf'));pdf.write_bytes(pdf.read_bytes()+b'changed')
        with patch.object(p,'GPU_MANIFEST',p.identity(ref)['sha256']),patch.object(p,'MODEL_MANIFEST',p.identity(models/'model_manifest.json')['sha256']):
            with self.assertRaisesRegex(ValueError,'Source checksum mismatch'):
                p.freeze_cohort(pp,data,self.root,runtime,ref,renderer,models,self.root/'cohort','no_known_prior_content_inspection')
        self.assertFalse((self.root/'cohort').exists())
    def test_freeze_refuses_unknown_inspection_before_reading_inputs(self):
        with self.assertRaisesRegex(ValueError,'additional exposure'):
            p.freeze_cohort('missing','missing','missing','missing','missing','missing','missing',self.root/'cohort','unconfirmed')
        self.assertFalse((self.root/'cohort').exists())

if __name__=='__main__':unittest.main()
