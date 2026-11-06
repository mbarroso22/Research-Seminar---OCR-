"""Setup-only regression tests; pip, CUDA and OCR are never executed."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('broader_runtime_repair',Path(__file__).resolve().parents[1]/'scripts/prepare_broader_inputs.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class BroaderRuntimeResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        versions={'cryptography':'50.0.2','paddleocr':'3.3.2','paddlex':'3.3.10','pip':'25.0.1',
                  'pypdf':'6.19.0','setuptools':'84.0.0','paddlepaddle-gpu':'3.3.0','numpy':'2.5.4'}
        self.expected={**versions,'htcondor':'25.10.1','financial-ocr-research':'0.2.0'}
        self.reference=self.root/'reference.json'
        p.save(self.reference,{'status':'complete','run_id':'2ceb1dc5ae404c01b65e7128ea5afb3b',
                               'contract':{'runtime':{'packages':self.expected}}})
        self.digest=p.identity(self.reference)['sha256']
        self.hash_patch=patch.object(p,'GPU_MANIFEST',self.digest);self.hash_patch.start();self.addCleanup(self.hash_patch.stop)
        environment={'os_name':'nt','sys_platform':'win32','platform_system':'Windows','python_full_version':'3.12.10',
                     'platform_python_implementation':'CPython','platform_machine':'AMD64'}
        self.report={'version':'1','pip_version':'25.0.1','environment':environment,'install':[]}
        for name,version in versions.items():
            filename=f'{name.replace("-","_")}-{version}-py3-none-any.whl'
            if name=='paddlepaddle-gpu':filename='paddlepaddle_gpu-3.3.0-cp312-cp312-win_amd64.whl'
            self.report['install'].append({'metadata':{'name':name,'version':version},
                'download_info':{'url':'https://example.invalid/'+filename,
                                 'archive_info':{'hashes':{'sha256':hashlib.sha256(filename.encode()).hexdigest()}}}})
        self.report_path=self.root/'pip-resolution.json';p.save(self.report_path,self.report)

    def tearDown(self):self.temp.cleanup()

    def test_linux_only_inventory_entry_is_not_an_install_requirement(self):
        before=self.reference.read_bytes();report_before=self.report_path.read_bytes()
        output=self.root/'resolved';result=p.validate_resolution(self.reference,self.report_path,output)
        self.assertEqual(result['status'],'resolution_verified')
        self.assertEqual(result['reference_inventory_not_selected'],{'htcondor':'25.10.1'})
        lock=(output/'gpu-active-wheel-lock.txt').read_text()
        self.assertIn('paddlepaddle-gpu==3.3.0 --hash=sha256:',lock)
        self.assertNotIn('htcondor',lock)
        download_lock=(output/'gpu-active-nonframework-wheel-lock.txt').read_text()
        self.assertIn('numpy==2.5.4 --hash=sha256:',download_lock)
        self.assertNotIn('paddlepaddle-gpu==',download_lock)
        self.assertEqual(self.reference.read_bytes(),before)
        self.assertEqual(self.report_path.read_bytes(),report_before)
        with self.assertRaises(FileExistsError):p.validate_resolution(self.reference,self.report_path,output)

    def assert_resolution_rejected(self,report,match):
        p.save(self.report_path,report);output=self.root/'rejected'
        with self.assertRaisesRegex(ValueError,match):p.validate_resolution(self.reference,self.report_path,output)
        self.assertFalse(output.exists())

    def test_required_package_version_drift_is_not_relaxed(self):
        self.report['install'][0]['metadata']['version']='99.0.0'
        self.assert_resolution_rejected(self.report,'pin changed')

    def test_unknown_transitive_package_is_rejected_before_installation(self):
        self.report['install'].append({'metadata':{'name':'new-unpinned-dependency','version':'1.0'}})
        self.assert_resolution_rejected(self.report,'no preserved runtime pin')

    def test_missing_explicit_root_and_wrong_gpu_abi_are_rejected(self):
        report=copy.deepcopy(self.report)
        report['install']=[i for i in report['install'] if i['metadata']['name']!='cryptography']
        self.assert_resolution_rejected(report,'missing an explicit root')
        report=copy.deepcopy(self.report)
        gpu=next(i for i in report['install'] if i['metadata']['name']=='paddlepaddle-gpu')
        gpu['download_info']['url']='https://example.invalid/paddlepaddle_gpu-3.3.0-cp313-cp313-win_amd64.whl'
        self.assert_resolution_rejected(report,'Wrong GPU wheel')

    def test_linux_report_and_changed_resolver_are_rejected(self):
        report=copy.deepcopy(self.report);report['environment']['sys_platform']='linux'
        self.assert_resolution_rejected(report,'native Windows')
        report=copy.deepcopy(self.report);report['pip_version']='26.2.2'
        self.assert_resolution_rejected(report,'Resolver pip version')

    def test_missing_hash_source_archive_and_duplicate_package_are_rejected(self):
        report=copy.deepcopy(self.report);report['install'][0]['download_info']['archive_info']['hashes']={}
        self.assert_resolution_rejected(report,'Missing wheel SHA-256')
        report=copy.deepcopy(self.report);report['install'][0]['download_info']['url']='https://example.invalid/source.tar.gz'
        self.assert_resolution_rejected(report,'non-wheel')
        report=copy.deepcopy(self.report);report['install'].append(copy.deepcopy(report['install'][0]))
        self.assert_resolution_rejected(report,'Duplicate resolved')

    def test_changed_reference_fails_without_outputs(self):
        self.reference.write_bytes(self.reference.read_bytes()+b' ')
        self.assert_resolution_rejected(self.report,'reference identity changed')

    def runtime_check(self,packages,output):
        import finocr
        repository=Path(finocr.__file__).resolve().parents[2]
        distributions=[types.SimpleNamespace(metadata={'Name':k},version=v) for k,v in packages.items()]
        paddle=types.SimpleNamespace(is_compiled_with_cuda=lambda:True,version=types.SimpleNamespace(cuda=lambda:'11.8'),
            set_device=Mock(),utils=types.SimpleNamespace(run_check=Mock()),
            device=types.SimpleNamespace(synchronize=Mock(),get_device=lambda:'gpu:0',cuda=types.SimpleNamespace(
                get_device_properties=lambda _:types.SimpleNamespace(major=8,minor=6,name='Mock GPU',total_memory=8192*1024*1024))))
        with patch.object(p.sys,'version_info',(3,12,10)),patch.object(p.metadata,'distributions',return_value=distributions),\
             patch.object(p.metadata,'version',side_effect=p.metadata.PackageNotFoundError),\
             patch.object(p.subprocess,'check_output',return_value='0, Mock GPU, 537.70, 8192, 7316'),\
             patch.dict(sys.modules,{'paddle':paddle}):
            result=p.check_runtime(self.reference,repository,output,self.report_path)
        return result,paddle

    def test_active_runtime_passes_with_unused_inventory_recorded_and_cuda_mocked(self):
        packages={k:v for k,v in self.expected.items() if k!='htcondor'}
        result,paddle=self.runtime_check(packages,self.root/'runtime.json')
        self.assertEqual(result['status'],'setup_complete')
        self.assertEqual(result['reference_inventory_not_selected'],{'htcondor':'25.10.1'})
        self.assertFalse(result['package_differences']);paddle.utils.run_check.assert_called_once()

    def test_missing_or_changed_active_package_still_fails_runtime_check(self):
        packages={k:v for k,v in self.expected.items() if k not in {'htcondor','numpy'}}
        output=self.root/'missing.json'
        with self.assertRaisesRegex(ValueError,'preserved GPU specification'):self.runtime_check(packages,output)
        self.assertIsNone(p.load(output)['package_differences']['numpy']['actual'])
        packages['numpy']='0.0';output=self.root/'changed.json'
        with self.assertRaisesRegex(ValueError,'preserved GPU specification'):self.runtime_check(packages,output)
        self.assertEqual(p.load(output)['status'],'failed')

    def test_extra_package_is_rejected_including_cpu_paddle(self):
        packages={k:v for k,v in self.expected.items() if k!='htcondor'}
        for name in ('unexpected-extra','paddlepaddle'):
            output=self.root/(name+'.json')
            with self.assertRaisesRegex(ValueError,'outside the resolved GPU dependency closure'):
                self.runtime_check({**packages,name:'3.3.0'},output)
            self.assertEqual(p.load(output)['status'],'failed')


if __name__=='__main__':unittest.main()
