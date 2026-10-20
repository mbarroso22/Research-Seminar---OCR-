"""Original-set closeout and failure exports using disposable files/mocked pip."""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from finocr_qualification.evidence import snapshot,write_json
from finocr_qualification.preservation import preservation_extension

REPO=Path(__file__).resolve().parents[1]


class PreservationCloseoutTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('closeout_fixture',REPO/'scripts/close_qualification_preservation.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        reviews=self.base/'reviews';reviews.mkdir()
        self.original=reviews/'mock-original';self.original.mkdir();before=self.original/'before';before.mkdir()
        self.compiler=reviews/'mock-compiler';self.compiler.mkdir();(self.compiler/'preparation').mkdir()
        files=self.base/'mock-tracked';files.mkdir()
        self.tracked=[files/f'{i:03d}.txt' for i in range(184)]
        for i,path in enumerate(self.tracked):path.write_text('MOCK TRACKED '+str(i))
        rows=''.join(str(p)+'\t'+self.module.file_sha(p).upper()+'\r\n' for p in self.tracked)
        (before/'preserved-hashes.txt').write_bytes(b'\xef\xbb\xbf'+rows.encode())
        for name in self.module.BEFORE_SHA256:
            if name!='preserved-hashes.txt':(before/name).write_bytes(b'\xef\xbb\xbfMockPackage==1.0\r\n')
        self.archives=(reviews/'mock-original.zip',reviews/'mock-compiler.zip')
        for path in self.archives:path.write_bytes(b'MOCK ORIGINAL ARCHIVE '+path.name.encode())
        self.preparation=self.compiler/'preparation/offline_preparation.json'
        write_json(self.preparation,{'protected':snapshot([files])})
        self.stack=ExitStack()
        self.stack.enter_context(patch.object(self.module,'BEFORE_SHA256',{
            p.name:self.module.file_sha(p) for p in before.iterdir()}))
        self.stack.enter_context(patch.object(self.module,'ARCHIVE_SHA256',tuple(self.module.file_sha(p) for p in self.archives)))
        self.stack.enter_context(patch.object(self.module,'PREDECESSOR_PREPARATION_SHA256',self.module.file_sha(self.preparation)))
        self.output=reviews/'mock-new-closeout';self.archive=reviews/'mock-new-closeout.zip'
        self.calls=[]
    def tearDown(self):self.stack.close();self.temp.cleanup()
    def mock_pip(self,command,**kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command,0,b'MockPackage==1.0\n',b'')
    def execute(self,runner=None):
        return self.module.closeout(REPO,self.original,self.compiler,self.archives,
            self.output,self.archive,inventory_runner=runner or self.mock_pip)
    def test_exact_184_and_three_inventories_pass_export_and_preserve_both_reviews_archives(self):
        protected=snapshot([self.original,self.compiler,*self.archives])
        result,export=self.execute()
        self.assertTrue(result['preservation_pass']);self.assertEqual(result['matched_tracked_files'],184)
        self.assertEqual(len(self.calls),3);self.assertTrue(export['verified'])
        self.assertTrue(all(c[1:]==['-m','pip','freeze','--all'] for c in self.calls))
        self.assertEqual(protected,snapshot([self.original,self.compiler,*self.archives]))
        with zipfile.ZipFile(self.archive) as archive:
            self.assertIsNone(archive.testzip());manifest=json.loads(archive.read('_EXPORT_MANIFEST.json'))
            self.assertIn('comparison.json',manifest['files'])
            self.assertEqual(hashlib.sha256(archive.read('comparison.json')).hexdigest(),manifest['files']['comparison.json'])
        self.assertEqual(result['remaining_authorized_requests'],0)
    def test_changed_tracked_file_retains_mismatch_and_exports_failure_without_rebaseline(self):
        original=(self.original/'before/preserved-hashes.txt').read_bytes()
        self.tracked[0].write_bytes(b'MOCK DRIFT')
        report,export=self.execute()
        self.assertFalse(report['preservation_pass']);self.assertEqual(report['matched_tracked_files'],183)
        self.assertEqual(report['mismatches'][0]['path'],str(self.tracked[0]));self.assertTrue(export['verified'])
        self.assertEqual(original,(self.original/'before/preserved-hashes.txt').read_bytes())
    def test_missing_tracked_file_is_explicit_and_does_not_shrink_denominator(self):
        self.tracked[0].unlink();report,export=self.execute()
        self.assertEqual(report['tracked_files'],184);self.assertEqual(report['matched_tracked_files'],183)
        self.assertIn('error',report['mismatches'][0]);self.assertTrue(export['verified'])
    def test_package_change_or_failed_inventory_is_not_a_preservation_pass(self):
        def changed(command,**kwargs):return subprocess.CompletedProcess(command,0,b'MockPackage==2.0\n',b'')
        report,_=self.execute(changed)
        self.assertFalse(report['preservation_pass']);self.assertFalse(any(r['matches_original_inventory'] for r in report['environment_inventories']))
    def test_inventory_failure_retains_stderr_and_failed_export(self):
        def failed(command,**kwargs):return subprocess.CompletedProcess(command,1,b'',b'MOCK PIP FAILURE')
        report,export=self.execute(failed)
        self.assertFalse(report['preservation_pass']);self.assertTrue(export['verified'])
        self.assertEqual(len(list((self.output/'final').glob('*.stderr.txt'))),3)
    def test_inventory_timeout_is_retained_without_installing_or_retrying(self):
        calls=[]
        def timeout(command,**kwargs):calls.append(command);raise subprocess.TimeoutExpired(command,60)
        report,_=self.execute(timeout)
        self.assertEqual(len(calls),3);self.assertFalse(report['preservation_pass'])
    def test_edited_untouched_before_set_is_rejected_without_creating_output(self):
        (self.original/'before/preserved-hashes.txt').write_bytes(b'MOCK REBASELINE')
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(self.output.exists());self.assertFalse(self.archive.exists())
    def test_changed_archive_or_compiler_preparation_is_rejected_before_output(self):
        self.archives[0].write_bytes(b'MOCK ALTERED ORIGINAL ZIP')
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(self.output.exists())
    def test_existing_output_or_archive_is_never_overwritten(self):
        self.archive.write_bytes(b'KEEP EXISTING EXPORT')
        with self.assertRaises(FileExistsError):self.execute()
        self.assertEqual(self.archive.read_bytes(),b'KEEP EXISTING EXPORT');self.assertFalse(self.output.exists())
    def test_output_cannot_be_nested_in_either_completed_review(self):
        self.output=self.original/'forbidden'
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(self.output.exists())
    def test_mutation_to_completed_review_during_inventory_is_recorded_as_failure(self):
        def mutate(command,**kwargs):
            (self.compiler/'mock-drift.txt').write_bytes(b'MOCK DRIFT')
            return self.mock_pip(command,**kwargs)
        report,_=self.execute(mutate)
        self.assertFalse(report['completed_reviews_and_archives_unchanged']);self.assertFalse(report['preservation_pass'])
    def test_original_record_parser_rejects_duplicates_and_wrong_count(self):
        with self.assertRaises(ValueError):self.module.tracked_set(b'/one\t'+b'a'*64+b'\n')
        line=(str(self.tracked[0])+'\t'+'a'*64+'\n').encode()
        with self.assertRaises(ValueError):self.module.tracked_set(line*184)
    def extension(self):
        original=self.original/'before/preserved-hashes.txt'
        with patch('finocr_qualification.preservation.ORIGINAL_SET_SHA256',self.module.file_sha(original)), \
             patch('finocr_qualification.preservation.ORIGINAL_INVENTORY_SHA256',{
                 p.name:self.module.file_sha(p) for p in original.parent.iterdir() if p.name!='preserved-hashes.txt'}):
            return preservation_extension(original,self.output)
    def test_preparation_extension_includes_all_underlying_184_files_not_only_snapshot_text(self):
        self.execute();paths,identity=self.extension()
        self.assertTrue(set(self.tracked).issubset(paths));self.assertEqual(len(paths),186)
        self.assertEqual(identity['tracked_files'],184);self.assertEqual(identity['environment_inventories'],3)
    def test_underlying_drift_after_closeout_is_rejected_before_preparation(self):
        self.execute();self.tracked[-1].write_bytes(b'MOCK LATER DRIFT')
        with self.assertRaises(ValueError):self.extension()
    def test_altered_closeout_inventory_cannot_be_accepted_from_summary_boolean(self):
        self.execute();name='Research-Seminar-OCR-current-.venv-ocr.txt'
        (self.output/'final'/name).write_bytes(b'MockPackage==2.0\n')
        with self.assertRaises(ValueError):self.extension()
    def test_closeout_copied_before_set_must_match_untouched_original_bytes(self):
        self.execute();(self.output/'original-before/preserved-hashes.txt').write_bytes(b'MOCK ALTERATION')
        with self.assertRaises(ValueError):self.extension()
    def test_failed_closeout_or_new_allowance_claim_is_rejected(self):
        self.execute();path=self.output/'comparison.json';report=json.loads(path.read_text())
        path.write_text(json.dumps({**report,'remaining_authorized_requests':6}))
        with self.assertRaises(ValueError):self.extension()
    def test_duplicate_or_missing_environment_inventory_is_rejected(self):
        self.execute();path=self.output/'comparison.json';report=json.loads(path.read_text())
        report['environment_inventories']=report['environment_inventories'][:2]
        path.write_text(json.dumps(report))
        with self.assertRaises(ValueError):self.extension()
