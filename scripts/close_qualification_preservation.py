"""Recapture the reviewed 184-file/three-environment set; export to NEW paths only.

Can run as a standalone downloaded file before applying the incremental patch.
Uses only the existing repository's evidence helpers and existing interpreters.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import os

BEFORE_SHA256 = {
    'preserved-hashes.txt':'b39668d3c883c28c6bfeeb9f4b1f58290c9c5d778db181ba4895d4cba2f7d73e',
    'Research-Seminar-OCR-current-.venv.txt':'9f44d59482d1884f853b6d61a6ecf9777d51fb3e83834d45976f84ae3ae24363',
    'Research-Seminar-OCR-current-.venv-ocr.txt':'3eac19eb8ba2f234932919cea3c6b4933c05fb752fb9cbe1cde1c229b38f452b',
    'Research-Seminar-OCR-review-.venv-answer.txt':'34d53b3eb793a0244dfb55b559c865f5528aee4cb098fdb6f62f7cc063f27848'}
ARCHIVE_SHA256 = ('36b338daed91b607024c3dd9cbd1c831e5c8bf269ecfff05b73126b2f7ef07ad',
                  '44c2558b2158259eb94b0664fd6bd012eaefb4462f464fc85f47e1e99c1b1913')
PREDECESSOR_PREPARATION_SHA256 = '597cd4ffd91f4e6046703067627e4a4421d623b58c8546d632f744f2f38242c4'


def file_sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def inventory_lines(raw):
    return sorted(raw.decode('utf-8-sig').splitlines(),key=lambda s:(s.casefold(),s))


def tracked_set(raw):
    entries={}
    for line in raw.decode('utf-8-sig').splitlines():
        parts=line.split('\t')
        if len(parts)!=2 or not re.fullmatch('[0-9a-fA-F]{64}',parts[1]):
            raise ValueError('Malformed original preservation inventory')
        path,expected=parts
        if not Path(path).is_absolute() or path.casefold() in {q.casefold() for q in entries}:
            raise ValueError('Original preservation paths must be absolute and unique')
        entries[path]=expected.lower()
    if len(entries)!=184:raise ValueError('Require exactly the original 184 tracked files')
    return entries


def closeout(repository, original_review, compiler_review, archives, output, archive,
             *, inventory_runner=subprocess.run):
    # Imports work with both the reviewed predecessor and this new increment.
    sys.path.insert(0,str(repository/'src'))
    from finocr_qualification.evidence import snapshot,assert_preserved,write_bytes,write_json,export_evidence
    repository,original_review,compiler_review,output,archive=(
        p.resolve() for p in (repository,original_review,compiler_review,output,archive))
    archives=tuple(p.resolve(strict=True) for p in archives)
    if len(archives)!=2 or compiler_review.parent!=original_review.parent:
        raise ValueError('Require both completed reviews and their two original archives')
    if output.parent!=original_review.parent or archive.parent!=original_review.parent:
        raise ValueError('Use new sibling paths under the existing reviews directory')
    before=original_review/'before'
    if {p.name for p in before.iterdir()}!=set(BEFORE_SHA256):
        raise ValueError('Untouched original before-set inventory differs')
    for name,expected in BEFORE_SHA256.items():
        if file_sha(before/name)!=expected:raise ValueError('Original before snapshot changed: '+name)
    for path,expected in zip(archives,ARCHIVE_SHA256):
        if file_sha(path)!=expected:raise ValueError('Reviewed archive identity differs: '+str(path))
    preparation=compiler_review/'preparation/offline_preparation.json'
    if file_sha(preparation)!=PREDECESSOR_PREPARATION_SHA256:
        raise ValueError('Compiler-followup preparation differs from the reviewed predecessor')
    predecessor=json.loads(preparation.read_text(encoding='utf-8-sig'))
    expected=tracked_set((before/'preserved-hashes.txt').read_bytes())
    roots=[original_review,compiler_review,*archives]
    for destination in (output,archive,archive.with_name(archive.name+'.sha256.json')):
        if destination.exists() or destination.is_symlink():raise FileExistsError('Never overwrite closeout evidence')
        for root in [repository,*roots]:
            if destination==root or root in destination.parents or destination in root.parents:
                raise ValueError('Closeout/export paths cannot overlap code or completed evidence')
    if output==archive or output in archive.parents or archive in output.parents:
        raise ValueError('Export must be outside the new closeout evidence directory')
    previous=snapshot(roots)
    output.mkdir()
    original=output/'original-before';original.mkdir()
    final=output/'final';final.mkdir()
    for name in BEFORE_SHA256:write_bytes(original/name,(before/name).read_bytes())
    write_json(output/'prior-evidence-before.json',previous)
    write_json(output/'capture-inputs.json',{'kind':'preservation_recapture_not_authorization',
        'repository':str(repository),'original_review':str(original_review),'compiler_review':str(compiler_review),
        'original_archives':[str(p) for p in archives],'tracked_file_count':184,
        'inference_executed':0,'additional_inference_authorized':0})
    mismatches=[];observed={}
    for name,wanted in expected.items():
        try:observed[name]=file_sha(Path(name))
        except OSError as exc:
            observed[name]=None;mismatches.append({'path':name,'error':str(exc),'expected':wanted})
            continue
        if observed[name]!=wanted:mismatches.append({'path':name,'expected':wanted,'actual':observed[name]})
    write_bytes(final/'preserved-hashes.txt',''.join(f'{p}\t{h or "MISSING"}\n' for p,h in observed.items()).encode())
    current=repository.parent/'Research-Seminar-OCR-current'
    specifications=[('Research-Seminar-OCR-current-.venv.txt',current/'.venv/Scripts/python.exe'),
        ('Research-Seminar-OCR-current-.venv-ocr.txt',current/'.venv-ocr/Scripts/python.exe'),
        ('Research-Seminar-OCR-review-.venv-answer.txt',repository/'.venv-answer/Scripts/python.exe')]
    inventories=[]
    for name,executable in specifications:
        row={'name':name,'interpreter':str(executable),'command':[str(executable),'-m','pip','freeze','--all']}
        stdout=b'';stderr=b''
        try:
            result=inventory_runner(row['command'],capture_output=True,timeout=60,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1'})
            stdout,stderr=result.stdout,result.stderr;row['exit_code']=result.returncode
            row['matches_original_inventory']=result.returncode==0 and inventory_lines(stdout)==inventory_lines((before/name).read_bytes())
        except (OSError,subprocess.TimeoutExpired,UnicodeError) as exc:
            row.update(error=str(exc),matches_original_inventory=False)
        write_bytes(final/name,stdout);write_bytes(final/(name+'.stderr.txt'),stderr)
        row['original_file_sha256']=file_sha(before/name);row['final_file_sha256']=file_sha(final/name)
        inventories.append(row)
    report={'kind':'final_preservation_comparison_not_authorization','tracked_files':184,
        'matched_tracked_files':sum(observed[p]==h for p,h in expected.items()),'mismatches':mismatches,
        'environment_inventories':inventories,'inference_executed':0,'additional_inference_authorized':0,
        'remaining_authorized_requests':0,
        'scope':'Exact original 184 files and three package inventories; cache manifests do not rehash every OCR byte'}
    try:
        write_json(output/'prior-evidence-after.json',assert_preserved(previous))
        report['completed_reviews_and_archives_unchanged']=True
    except (OSError,ValueError) as exc:
        report.update(completed_reviews_and_archives_unchanged=False,previous_evidence_error=str(exc))
    try:
        assert_preserved(predecessor['protected']);report['compiler_preparation_protected_roots_unchanged']=True
    except (OSError,ValueError) as exc:
        report.update(compiler_preparation_protected_roots_unchanged=False,compiler_preservation_error=str(exc))
    report['preservation_pass']=bool(not mismatches and all(v['matches_original_inventory'] for v in inventories)
        and report['completed_reviews_and_archives_unchanged'] and report['compiler_preparation_protected_roots_unchanged'])
    write_json(output/'comparison.json',report)
    exported=export_evidence(output,archive)
    return report,exported


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['repository','original-review','compiler-review','original-archive','compiler-archive','output','archive']:
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    try:
        report,exported=closeout(args.repository,args.original_review,args.compiler_review,
            (args.original_archive,args.compiler_archive),args.output,args.archive)
        print(json.dumps({'status':'preservation_pass' if report['preservation_pass'] else 'preservation_failed',
            'tracked_files':report['tracked_files'],'matched_tracked_files':report['matched_tracked_files'],
            'environment_inventories':len(report['environment_inventories']),'export':exported,
            'inference_executed':0,'additional_inference_authorized':0},indent=2))
        return 0 if report['preservation_pass'] else 2
    except Exception as exc:
        print(json.dumps({'status':'closeout_failed','error':f'{type(exc).__name__}: {exc}',
            'preserve_partial_output':True,'inference_executed':0,'additional_inference_authorized':0},indent=2))
        return 2


if __name__=='__main__':raise SystemExit(main())
