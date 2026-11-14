"""v8 inputs with frozen v3 binding/arithmetic; references never enter inference."""
import copy
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'component'))
from legacy import binding_v2,pipeline_v6
from binding_v3 import bind_answer
from pipeline_v3 import calculate_bound


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def strict_contract(text):
    try:
        raw=json.loads(text,object_pairs_hook=pipeline_v6.unique_object,parse_constant=pipeline_v6.reject_constant,parse_float=pipeline_v6.finite_float)
        if not isinstance(raw,dict) or set(raw)!={'answer','unit','source_values','evidence_pages','abstain','explanation'}:return False
        if type(raw['answer']) not in (int,float,str,type(None)) or type(raw['abstain']) is not bool:return False
        if type(raw['answer']) is float and not math.isfinite(raw['answer']):return False
        if not all(isinstance(raw[k],str) for k in ['unit','explanation']):return False
        if not isinstance(raw['evidence_pages'],list) or any(type(p) is not int for p in raw['evidence_pages']):return False
        if not isinstance(raw['source_values'],list):return False
        for f in raw['source_values']:
            if not isinstance(f,dict) or set(f)!={'label','value','year','unit','pdf_page_index'}:return False
            if not isinstance(f['label'],str) or not isinstance(f['unit'],str):return False
            if type(f['year']) is not int or type(f['pdf_page_index']) is not int or type(f['value']) not in (int,float):return False
            if not math.isfinite(f['value']):return False
        return True
    except (ValueError,TypeError,OverflowError):return False


def postprocess(text,case,assets,prepared):
    supplied=[assets[k]['pdf_page_index'] for k in case['page_assets']]
    raw,issues=pipeline_v6.parse_schema(text,supplied)
    result={'runner_version':8,'table_binding_version':3,'raw_answer_text':text,
            'raw_answer_text_sha256':pipeline_v6.digest(text.encode()),'raw_answer_record':copy.deepcopy(raw),
            'schema_issues':issues,'source_verified':False,'candidate_answer':None,'table_binding':None}
    def finish(status,reasons,calc=None):
        result['evidence_gate']={'release_status':status,'problems':reasons,'source_verified':False}
        result['calculator_result']=calc or {'status':'preserved_abstention' if status=='abstained' else 'skipped_schema_hold' if issues else 'skipped_evidence_hold','calculator_executed':False}
        return result
    if isinstance(raw,dict) and raw.get('abstain') is True:return finish('abstained',issues)
    if issues:return finish('held_for_review',issues)
    for key in case['page_assets']:
        asset=assets[key];path=(prepared/asset['text']).resolve()
        if prepared.resolve() not in path.parents or asset['doc_id']!=case['doc_id']:raise ValueError('Source identity mismatch')
        if pipeline_v6.digest(path.read_bytes())!=asset['text_sha256']:raise ValueError('Source text changed')
    spec=copy.deepcopy(read(ROOT/'calculation_registry.json')['specifications'][case['case_id']])
    for role in spec['roles']:role['allowed_pages']=supplied
    metrics=read(ROOT/'table_roles.json')['roles'][case['case_id']]
    cache=binding_v2.validate_layout_cache(read(ROOT/'fixtures/layout_pages.json'),assets)
    context=read(ROOT/'document_contexts.json')[case['doc_id']]
    binding=bind_answer(raw,spec,metrics,case['doc_id'],supplied,cache,context,{})
    result['table_binding']=binding
    if binding['status']!='table_cell_match':return finish('held_for_review',binding['reasons'])
    calculation=calculate_bound(raw,spec,binding)
    if calculation['status']!='calculated':return finish('held_for_review',['calculator_declined'],calculation)
    if calculation['answer']['source_values']!=raw['source_values'] or calculation['answer']['evidence_pages']!=raw['evidence_pages']:
        raise ValueError('Calculator changed original evidence')
    result['candidate_answer']=calculation['answer']
    return finish('table_cell_match_unverified',[],calculation)
