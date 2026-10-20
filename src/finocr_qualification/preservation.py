"""Bind the final closeout AND its original underlying files into preparation."""
import hashlib
from pathlib import Path
import re

from finocr_answer.contract import strict_json
from finocr_answer.setup import sha

ORIGINAL_SET_SHA256='b39668d3c883c28c6bfeeb9f4b1f58290c9c5d778db181ba4895d4cba2f7d73e'
INVENTORIES=('Research-Seminar-OCR-current-.venv.txt',
             'Research-Seminar-OCR-current-.venv-ocr.txt',
             'Research-Seminar-OCR-review-.venv-answer.txt')
ORIGINAL_INVENTORY_SHA256={
    INVENTORIES[0]:'9f44d59482d1884f853b6d61a6ecf9777d51fb3e83834d45976f84ae3ae24363',
    INVENTORIES[1]:'3eac19eb8ba2f234932919cea3c6b4933c05fb752fb9cbe1cde1c229b38f452b',
    INVENTORIES[2]:'34d53b3eb793a0244dfb55b559c865f5528aee4cb098fdb6f62f7cc063f27848'}


def preservation_extension(original: Path, closeout: Path):
    original,closeout=original.resolve(strict=True),closeout.resolve(strict=True)
    raw=original.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SET_SHA256:
        raise ValueError('Require untouched reviewed original 184-file preservation set')
    if (closeout/'original-before/preserved-hashes.txt').read_bytes()!=raw:
        raise ValueError('Final closeout was not compared to the same original before set')
    entries={}
    for line in raw.decode('utf-8-sig').splitlines():
        parts=line.split('\t')
        if len(parts)!=2 or not re.fullmatch('[0-9a-fA-F]{64}',parts[1]):
            raise ValueError('Invalid original preservation record')
        path,value=parts
        if not Path(path).is_absolute() or path.casefold() in entries:
            raise ValueError('Original preservation paths must be absolute/unique')
        entries[path.casefold()]=(Path(path).resolve(strict=True),value.lower())
    if len(entries)!=184:raise ValueError('Exactly 184 original preservation files required')
    for path,value in entries.values():
        if sha(path)!=value:raise ValueError('Original underlying preserved file changed: '+str(path))
    report=strict_json((closeout/'comparison.json').read_text(encoding='utf-8-sig'))
    if (report['kind']!='final_preservation_comparison_not_authorization' or
        report['preservation_pass'] is not True or report['tracked_files']!=184 or
        report['matched_tracked_files']!=184 or report['mismatches'] or
        report['completed_reviews_and_archives_unchanged'] is not True or
        report['compiler_preparation_protected_roots_unchanged'] is not True or
        any(type(report[k]) is not int or report[k]!=0 for k in (
            'inference_executed','additional_inference_authorized','remaining_authorized_requests'))):
        raise ValueError('Complete passing final preservation closeout required')
    rows=report['environment_inventories']
    if len(rows)!=3 or {r['name'] for r in rows}!=set(INVENTORIES):
        raise ValueError('Require exactly all three original environment inventories')
    normalized=lambda data:sorted(data.decode('utf-8-sig').splitlines())
    for row in rows:
        name=row['name'];before=closeout/'original-before'/name;after=closeout/'final'/name
        if (row['matches_original_inventory'] is not True or row.get('exit_code')!=0 or
            sha(original.parent/name)!=ORIGINAL_INVENTORY_SHA256[name] or
            sha(before)!=row['original_file_sha256'] or sha(after)!=row['final_file_sha256'] or
            normalized(before.read_bytes())!=normalized(after.read_bytes()) or
            before.read_bytes()!=(original.parent/name).read_bytes()):
            raise ValueError('Final environment inventory mismatch: '+name)
    paths=[original,closeout,*[path for path,_ in entries.values()]]
    identity={'original_preservation_set':str(original),'original_sha256':ORIGINAL_SET_SHA256,
        'closeout_directory':str(closeout),'comparison_sha256':sha(closeout/'comparison.json'),
        'tracked_files':184,'environment_inventories':3}
    return paths,identity
