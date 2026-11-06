"""Input preparation for the existing OCR/retrieval CLI; no OCR or ranking here."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zipfile

GPU_MANIFEST = 'c79e71c736ca6fe1f33d3fc7cdae039f212d01a094a209c3cd9eb17324afcf0d'
MODEL_MANIFEST = 'd0a91a2378b843c0fcc3ea007e4505072277b55f3b6aa07ffab15c3af8a07cf4'
GROUP = 'company_disjoint_evaluation'
ACTIVE_ROOTS = ('cryptography', 'paddleocr', 'paddlex', 'pip', 'pypdf', 'setuptools')

def identity(path):
    p=Path(path);h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return {'sha256':h.hexdigest(),'size_bytes':p.stat().st_size}

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
def require(ok,message):
    if not ok:raise ValueError(message)

def package_name(name):
    return re.sub(r'[-_.]+', '-', name).lower()

def reference_packages(reference):
    require(identity(reference)['sha256']==GPU_MANIFEST,'GPU reference identity changed')
    manifest=load(reference)
    require(manifest['status']=='complete' and manifest['run_id']=='2ceb1dc5ae404c01b65e7128ea5afb3b','Wrong completed GPU reference')
    packages={package_name(k):v for k,v in manifest['contract']['runtime']['packages'].items()}
    require(packages.get('paddlepaddle-gpu')=='3.3.0' and 'paddlepaddle' not in packages,'Wrong GPU framework specification')
    return packages

def resolution_packages(reference,report):
    """Check pip's Windows dependency resolution without editing historical pins."""
    expected=reference_packages(reference);resolution=load(report)
    require(resolution.get('version')=='1','Unsupported pip resolution report')
    require(resolution.get('pip_version')==expected['pip'],'Resolver pip version changed')
    environment=resolution.get('environment',{})
    required_environment={'os_name':'nt','sys_platform':'win32','platform_system':'Windows',
                          'python_full_version':'3.12.10','platform_python_implementation':'CPython'}
    require(all(environment.get(k)==v for k,v in required_environment.items()),'Use a native Windows Python 3.12.10 resolution report')
    require(environment.get('platform_machine','').lower() in {'amd64','x86_64'},'Use Windows x64')
    selected={};hashes={}
    for item in resolution.get('install',[]):
        name=package_name(item['metadata']['name']);version=item['metadata']['version']
        require(name not in selected,f'Duplicate resolved package: {name}')
        require(name in expected and name!='financial-ocr-research',f'Resolved package has no preserved runtime pin: {name}')
        require(version==expected[name],f'Resolved package pin changed: {name}')
        download=item.get('download_info',{});filename=unquote(urlsplit(download.get('url','')).path).rsplit('/',1)[-1]
        require(filename.lower().endswith('.whl'),f'Resolution requires a non-wheel distribution: {name}')
        digest=download.get('archive_info',{}).get('hashes',{}).get('sha256','')
        require(re.fullmatch(r'[0-9a-f]{64}',digest) is not None,f'Missing wheel SHA-256: {name}')
        if name=='paddlepaddle-gpu':
            require(filename=='paddlepaddle_gpu-3.3.0-cp312-cp312-win_amd64.whl','Wrong GPU wheel platform or Python ABI')
        selected[name]=version;hashes[name]=digest
    require(set(ACTIVE_ROOTS)|{'paddlepaddle-gpu'} <= selected.keys(),'Resolved runtime is missing an explicit root package; use --ignore-installed')
    return expected,selected,hashes

def validate_resolution(reference,report,output):
    expected,selected,hashes=resolution_packages(reference,report)
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    lock=out/'gpu-active-wheel-lock.txt'
    lock.write_text('# Windows OCR dependency closure resolved under unchanged historical constraints\n'+
                    '\n'.join(f'{name}=={version} --hash=sha256:{hashes[name]}' for name,version in sorted(selected.items()))+'\n',
                    encoding='utf-8',newline='\n')
    (out/'gpu-active-nonframework-wheel-lock.txt').write_text(
        '# Already resolved non-framework wheels; retain the separately downloaded official cu118 GPU wheel\n'+
        '\n'.join(f'{name}=={version} --hash=sha256:{hashes[name]}' for name,version in sorted(selected.items()) if name!='paddlepaddle-gpu')+'\n',
        encoding='utf-8',newline='\n')
    result={'status':'resolution_verified','interpretation':'setup dependency resolution; no OCR, retrieval or LLM inference',
            'reference_manifest':identity(reference),'resolution_report':identity(report),
            'required_roots':list(ACTIVE_ROOTS)+['paddlepaddle-gpu'],'selected_packages':selected,
            'reference_inventory_not_selected':{k:v for k,v in expected.items() if k not in selected and k!='financial-ocr-research'},
            'wheel_lock':identity(lock),'output':str(out)}
    save(out/'resolution-review.json',result)
    return result

def find_reference(root):
    root=Path(root)
    require(root.is_dir(),'Preserved GPU import directory is missing')
    for p in sorted(root.rglob('run_manifest.json')):
        b=p.read_bytes()
        if hashlib.sha256(b).hexdigest()==GPU_MANIFEST:return b,{'file':str(p)}
    for p in sorted(root.rglob('*.zip')):
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if name.replace('\\','/').endswith('/run_manifest.json') or name=='run_manifest.json':
                    b=z.read(name)
                    if hashlib.sha256(b).hexdigest()==GPU_MANIFEST:return b,{'archive':str(p),'member':name}
    raise ValueError('The verified completed GPU manifest was not found; retain imports and supply the preserved full GPU archive. Do not substitute a CPU manifest.')

def export_runtime(imports,output):
    data,location=find_reference(imports);m=json.loads(data)
    require(m['status']=='complete' and m['run_id']=='2ceb1dc5ae404c01b65e7128ea5afb3b','Wrong completed GPU reference')
    packages=m['contract']['runtime']['packages']
    require(packages.get('paddlepaddle-gpu')=='3.3.0' and 'paddlepaddle' not in packages,'Wrong GPU framework specification')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/'gpu-reference-manifest.json').write_bytes(data)
    excluded={'paddlepaddle-gpu','financial-ocr-research'}
    pins=[f'{name}=={version}' for name,version in sorted(packages.items()) if name not in excluded]
    (out/'gpu-nonframework-exact.txt').write_text('# Exact packages from the verified completed GPU run; not latest versions\n'+'\n'.join(pins)+'\n',encoding='utf-8',newline='\n')
    save(out/'reference-origin.json',{'source':location,'manifest':identity(out/'gpu-reference-manifest.json'),'exported_pins':len(pins),'required_paddle':'paddlepaddle-gpu==3.3.0 from official cu118 channel'})
    return {'status':'pins_exported','packages':len(pins),'output':str(out)}

def check_runtime(reference,repository,output,resolution_report=None):
    require(not Path(output).exists(),'Use a new runtime-check output file')
    result={'stage':'gpu_setup_check','interpretation':'setup observations; no OCR, retrieval or LLM inference','status':'failed'}
    try:
        require(identity(reference)['sha256']==GPU_MANIFEST,'GPU reference identity changed')
        require(sys.version_info[:3]==(3,12,10),'Use Python 3.12.10')
        import finocr
        require(Path(finocr.__file__).resolve().parents[2]==Path(repository).resolve(),'Environment imports a different checkout')
        expected=load(reference)['contract']['runtime']['packages']
        if resolution_report is not None:
            historical,expected,_=resolution_packages(reference,resolution_report)
            actual={package_name(d.metadata['Name']):d.version for d in metadata.distributions()}
            result.update(dependency_policy='pip-resolved Windows OCR closure with unchanged historical version constraints',
                          resolution_report=identity(resolution_report),
                          reference_inventory_not_selected={k:v for k,v in historical.items() if k not in expected and k!='financial-ocr-research'})
            unexpected={k:v for k,v in actual.items() if k not in expected and k!='financial-ocr-research'}
            result['unexpected_installed_packages']=unexpected
            require(not unexpected,'Unexpected packages outside the resolved GPU dependency closure')
        else:
            actual={}
            for name in expected:
                try:actual[name]=metadata.version(name)
                except metadata.PackageNotFoundError:actual[name]=None
        differences={k:{'expected':v,'actual':actual.get(k)} for k,v in expected.items() if k!='financial-ocr-research' and actual.get(k)!=v}
        result.update(python=sys.version,executable=sys.executable,packages=actual,package_differences=differences)
        require(not differences,'Installed packages differ from the preserved GPU specification')
        try:metadata.version('paddlepaddle')
        except metadata.PackageNotFoundError:pass
        else:raise ValueError('CPU Paddle distribution must not be installed in the new GPU environment')
        result['nvidia_smi']=subprocess.check_output(['nvidia-smi','--query-gpu=index,name,driver_version,memory.total,memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
        driver=result['nvidia_smi'][0].split(',')[2].strip()
        require(tuple(map(int,driver.split('.')))>=(522,6),'Driver is below the CUDA 11.8 Windows requirement')
        import paddle
        require(paddle.is_compiled_with_cuda() and paddle.version.cuda()=='11.8','Expected the CUDA 11.8 GPU build; no CPU fallback')
        paddle.set_device('gpu:0');paddle.utils.run_check();paddle.device.synchronize('gpu:0')
        props=paddle.device.cuda.get_device_properties(0)
        require((props.major,props.minor)>=(7,5),'Unsupported GPU compute capability')
        result.update(status='setup_complete',paddle_device=paddle.device.get_device(),cuda=paddle.version.cuda(),gpu_name=props.name,total_vram_bytes=props.total_memory)
    except BaseException as exc:
        result['error']=f'{type(exc).__name__}: {exc}';raise
    finally:save(output,result)
    return result

def freeze_cohort(proposal_path,data_root,repository,runtime_path,reference,renderer,models,output,inspection_history):
    require(inspection_history=='no_known_prior_content_inspection','Record any additional exposure before freezing; select a different whole-company cohort first')
    from pypdf import PdfReader
    from finocr.pipelines.native_baseline import code_provenance
    from finocr.pipelines.ocr_device import device_condition
    from finocr.pipelines.report_rendering import renderer_identity
    from finocr.io import write_jsonl
    proposal=load(proposal_path);data=Path(data_root);root=Path(repository).resolve();out=Path(output)
    require(not out.exists(),'Frozen cohort output already exists; retain it')
    require(load(runtime_path)['status']=='setup_complete','Complete the GPU setup check first')
    require(identity(reference)['sha256']==GPU_MANIFEST,'GPU reference identity changed')
    reference_json=load(reference)
    renderer_data=renderer_identity(renderer)
    old_renderer=reference_json['contract']['render_contract']['renderer']
    require(all(renderer_data[k]==old_renderer[k] for k in ('version_output','binary_identities')),'Use the preserved Poppler binary and DLL bundle')
    configuration,pins=device_condition('gpu:0')
    require(configuration==reference_json['contract']['configuration'] and pins==reference_json['contract']['package_pins'],'OCR settings differ from the frozen GPU condition')
    require(identity(Path(models)/'model_manifest.json')['sha256']==MODEL_MANIFEST,'Existing model manifest changed')
    for name,info in proposal['required_source_files'].items():
        require(identity(data/'raw/financebench/data'/name)['sha256']==info['sha256'],f'Release source changed: {name}')
    source_meta=[json.loads(s) for s in (data/'raw/financebench/data/financebench_document_information.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    source_q=[json.loads(s) for s in (data/'raw/financebench/data/financebench_open_source.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    by_id={q['financebench_id']:q for q in source_q};require(len(by_id)==len(source_q),'Duplicate source question IDs')
    selected_ids={q for d in proposal['documents'] for q in d['question_ids']}
    companies={d['company'] for d in proposal['documents']}
    annual={r['doc_name'] for r in source_meta if r['company'] in companies and r['doc_type'].lower() in {'10k','10k_annualreport'}}
    require({q['financebench_id'] for q in source_q if q['doc_name'] in annual}==selected_ids,'Company-wide annual question coverage differs from proposal')
    docs=[];tasks=[];pdf_checks=[]
    for d in proposal['documents']:
        p=data/'raw/financebench/pdfs'/d['pdf_basename'];before=identity(p)
        require(before['sha256']==d['pdf_sha256'],f'Source checksum mismatch: {d["doc_id"]}')
        with p.open('rb') as f:
            reader=PdfReader(f,strict=False)
            if reader.is_encrypted:require(bool(reader.decrypt('')),f'Cannot decrypt source PDF: {d["doc_id"]}')
            require(len(reader.pages)==d['expected_pages'],f'Source page count mismatch: {d["doc_id"]}')
        require(identity(p)==before,'Source PDF changed during preflight')
        pdf_checks.append({'doc_id':d['doc_id'],'identity':before,'pages':d['expected_pages']})
        docs.append({'dataset':'financebench','doc_id':d['doc_id'],'pdf_path':str(p.resolve()),'source_path':str(p.resolve()),'source_format':'pdf','split':GROUP,'page_count':d['expected_pages'],'metadata':{'company':d['company'],'fiscal_year':d['fiscal_year'],'doc_type':'10k','sha256':d['pdf_sha256']}})
        for qid in d['question_ids']:
            q=by_id[qid];require(q['doc_name']==d['doc_name'],'Question/report mapping differs')
            require(all(e.get('evidence_doc_name',e.get('doc_name',d['doc_name']))==d['doc_name'] for e in q['evidence']),'Cross-report annotation needs review before freezing')
            pages=sorted({e['evidence_page_num'] for e in q['evidence']})
            require(pages and all(type(p) is int and 0<=p<d['expected_pages'] for p in pages),'Invalid zero-based evidence index')
            tasks.append({'task_id':'financebench:'+qid,'doc_id':d['doc_id'],'question':q['question'],'evidence_pages':pages})
    totals={'documents':len(docs),'pages':sum(d['page_count'] for d in docs),'questions':len(tasks),'multipage_questions':sum(len(t['evidence_pages'])>1 for t in tasks)}
    target=proposal['totals']
    require(totals=={'documents':target['question_bearing_reports'],'pages':target['pages'],'questions':target['questions'],'multipage_questions':target['multipage_questions']},'Cohort totals changed')
    out.mkdir(parents=True,exist_ok=False)
    write_jsonl(out/'documents.jsonl',docs);write_jsonl(out/'tasks.jsonl',tasks)
    write_jsonl(out/'retrieval-queries.jsonl',[{k:t[k] for k in ('task_id','doc_id','question')} for t in tasks])
    freeze={'stage':'company_cohort_freeze','frozen_utc':datetime.now(timezone.utc).isoformat(),'experimental_group':GROUP,'inspection_history':inspection_history,'totals':totals,'companies':sorted(companies),'all_company_years_reserved':proposal['reserved_company_annual_doc_names'],'settings':proposal['settings_to_freeze'],'ocr_configuration':configuration,'package_pins':pins,'code':code_provenance(root),'renderer':renderer_data,'model_manifest':identity(Path(models)/'model_manifest.json'),'runtime_check':identity(runtime_path),'reference_manifest':identity(reference),'proposal':identity(proposal_path),'preparation_script':identity(__file__),'pdf_checks':pdf_checks,'artifacts':{p.name:identity(p) for p in out.iterdir()}}
    save(out/'cohort-freeze.json',freeze)
    return {'status':'cohort_frozen','experimental_group':GROUP,**totals,'output':str(out)}

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    exp=sub.add_parser('export-runtime');exp.add_argument('--imports',required=True);exp.add_argument('--output-dir',required=True)
    resolution=sub.add_parser('validate-resolution');resolution.add_argument('--reference',required=True);resolution.add_argument('--report',required=True);resolution.add_argument('--output-dir',required=True)
    check=sub.add_parser('check-runtime');check.add_argument('--reference',required=True);check.add_argument('--repository',required=True);check.add_argument('--output',required=True);check.add_argument('--resolution-report')
    freeze=sub.add_parser('freeze-cohort')
    for name in ['proposal','data-root','repository','runtime-check','reference','renderer','models','output-dir']:
        freeze.add_argument('--'+name,required=True)
    freeze.add_argument('--inspection-history',choices=['no_known_prior_content_inspection'],required=True,help='Research exposure fact, not an execution authorization')
    a=parser.parse_args()
    if a.command=='export-runtime':result=export_runtime(a.imports,a.output_dir)
    elif a.command=='validate-resolution':result=validate_resolution(a.reference,a.report,a.output_dir)
    elif a.command=='check-runtime':result=check_runtime(a.reference,a.repository,a.output,a.resolution_report)
    else:result=freeze_cohort(a.proposal,a.data_root,a.repository,a.runtime_check,a.reference,a.renderer,a.models,a.output_dir,a.inspection_history)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
