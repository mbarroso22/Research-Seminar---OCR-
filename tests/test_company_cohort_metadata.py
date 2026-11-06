"""Cohort designation must not change frozen retrieval or default behavior."""
import unittest
from finocr.cli import build_parser
from finocr.io import read_json, read_jsonl, write_json
from finocr.pipelines.native_baseline import run_native_baseline
from finocr.pipelines.stopword_comparison import compare_stopwords, compare_query_expansion
from finocr.pipelines.ocr_comparison import compare_native_ocr
import test_full_ocr as fixtures

GROUP = 'company_disjoint_evaluation'

class CompanyCohortMetadataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.FullOcrTests(methodName='runTest')
        self.fixture.setUp()
    def tearDown(self): self.fixture.tearDown()
    def test_default_group_and_cli_default_are_preserved(self):
        f=self.fixture
        self.assertEqual(read_json(f.native/'run_manifest.json')['experimental_group'],'development_pilot')
        args=build_parser().parse_args(['native-baseline','--documents','d','--tasks','t','--output-dir','o'])
        self.assertEqual(args.experimental_group,'development_pilot')
    def test_invalid_group_fails_before_output(self):
        f=self.fixture; out=f.root/'invalid'
        with self.assertRaisesRegex(ValueError,'experimental group'):
            run_native_baseline(f.documents,f.tasks,out,repository_root=f.root,experimental_group='unrecognized')
        self.assertFalse(out.exists())
    def test_group_propagates_without_changing_scores_or_candidates(self):
        f=self.fixture; native=f.root/'new-native'; stop=f.root/'new-stop'; exp=f.root/'new-expansion'
        run_native_baseline(f.documents,f.tasks,native,repository_root=f.root,experimental_group=GROUP)
        compare_stopwords(native,stop,repository_root=f.root)
        compare_query_expansion(native,stop,exp,repository_root=f.root)
        for new,old,name in [(native,f.native,'retrieval_predictions.jsonl'),(stop,f.stop,'stopword_predictions.jsonl'),(exp,f.expansion,'expanded_predictions.jsonl')]:
            self.assertEqual(read_json(new/'run_manifest.json')['experimental_group'],GROUP)
            self.assertEqual([r['ranked_pages'] for r in read_jsonl(new/name)],[r['ranked_pages'] for r in read_jsonl(old/name)])
        self.assertNotIn('development-only',read_json(exp/'comparison_metrics.json')['interpretation'])
    def test_matched_group_propagates_and_scores_match_default(self):
        f=self.fixture
        # Metadata is inherited through a fresh source lineage before rendering.
        f.native=f.root/'new-native'; f.stop=f.root/'new-stop'; f.expansion=f.root/'new-expansion'
        run_native_baseline(f.documents,f.tasks,f.native,repository_root=f.root,experimental_group=GROUP)
        compare_stopwords(f.native,f.stop,repository_root=f.root)
        compare_query_expansion(f.native,f.stop,f.expansion,repository_root=f.root)
        from unittest.mock import patch
        from finocr.pipelines.report_rendering import render_full_reports
        import subprocess
        f.render=f.root/'new-render'
        def render(command,**kwargs):
            from pathlib import Path
            Path(command[-1]).with_suffix('.png').write_bytes(fixtures.fixture_png())
            return subprocess.CompletedProcess(command,0,'','')
        with patch('finocr.pipelines.report_rendering.renderer_identity',return_value={'fixture':True}), patch('finocr.pipelines.report_rendering.code_provenance',return_value={'fixture':True}), patch('finocr.pipelines.report_rendering.subprocess.run',side_effect=render):
            render_full_reports(f.documents,f.render,renderer_path='fixture',native_dir=f.native,repository_root=f.root)
        f.run_ocr(); f.compare()
        self.assertEqual(read_json(f.root/'comparison/run_manifest.json')['experimental_group'],GROUP)
        metrics=read_json(f.root/'comparison/comparison_metrics.json')
        self.assertNotIn('label-exposed development pilot',metrics['interpretation'])
        self.assertEqual(metrics['native'],read_json(f.expansion/'comparison_metrics.json')['question_expansion'])
    def test_mismatched_reference_group_rejected_before_output(self):
        f=self.fixture; f.run_ocr()
        p=f.expansion/'run_manifest.json';m=read_json(p);m['experimental_group']=GROUP;write_json(p,m)
        with self.assertRaisesRegex(ValueError,'experimental group mismatch'):
            compare_native_ocr(f.native,f.expansion,f.ocr,f.root/'rejected',repository_root=f.root)
        self.assertFalse((f.root/'rejected').exists())

if __name__=='__main__': unittest.main()
