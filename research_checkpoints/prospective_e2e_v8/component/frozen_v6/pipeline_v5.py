"""Version 5: schema -> source identity -> table binding v2 -> calculator v4.

Pure local postprocessing. An evidence-held record never enters the calculator. The raw
response is preserved separately from the unverified derived candidate.
"""
import copy
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path

from pilot_calculator import calculate_v4 as calculate_v3
from calculator_v2 import normalize_year
from evidence_screen import literal_present
from io_utils import digest,read,require
from table_binding import bind_answer,validate_layout_cache

ROOT=Path(__file__).resolve().parent

def reject_constant(value):
    raise ValueError('Non-finite JSON constant')

def finite_float(value):
    number=float(value)
    if not math.isfinite(number):
        raise ValueError('Non-finite JSON number')
    return number

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key]=value
    return result

def parse_schema(text,supplied):
    try:
        raw=json.loads(text,parse_constant=reject_constant,parse_float=finite_float,object_pairs_hook=unique_object)
        if not isinstance(raw,dict):
            raise ValueError('Object required')
    except (ValueError,TypeError):
        return None,['invalid_json_object']
    issues=[]
    if 'answer' not in raw or type(raw['answer']) is bool or isinstance(raw['answer'],list):
        issues.append('invalid_final_answer_field')
    if type(raw.get('abstain')) is not bool:
        issues.append('invalid_abstention_flag')
    for key in ['unit','explanation']:
        if not isinstance(raw.get(key),str):
            issues.append('invalid_'+key)
    evidence=raw.get('evidence_pages')
    if not isinstance(evidence,list):
        issues.append('invalid_evidence_pages')
    elif any(type(p) is not int or p not in supplied for p in evidence):
        issues.append('unsupplied_evidence_page')
    elif len(set(evidence))!=len(evidence):
        issues.append('duplicate_evidence_page')
    if raw.get('abstain') is False and not evidence:
        issues.append('answered_without_citation')
    fields=raw.get('source_values')
    if not isinstance(fields,list):
        issues.append('invalid_source_values')
        fields=[]
    if raw.get('abstain') is False and not fields:
        issues.append('missing_source_values')
    for i,v in enumerate(fields):
        prefix=f'field_{i}:'
        if not isinstance(v,dict) or any(k not in v for k in ['label','value','year','unit','pdf_page_index']):
            issues.append(prefix+'incomplete_source_field')
            continue
        if not isinstance(v['label'],str) or not v['label'].strip():
            issues.append(prefix+'invalid_label')
        if not isinstance(v['unit'],str) or not v['unit'].strip():
            issues.append(prefix+'missing_unit')
        try:
            if type(v['value']) not in (int,float) or not Decimal(str(v['value'])).is_finite():
                issues.append(prefix+'invalid_numeric_amount')
        except InvalidOperation:
            issues.append(prefix+'invalid_numeric_amount')
        try:
            normalize_year(v['year'])
        except ValueError:
            issues.append(prefix+'ambiguous_or_missing_year')
        p=v['pdf_page_index']
        if type(p) is not int or p not in supplied:
            issues.append(prefix+'unsupplied_source_page')
        elif isinstance(evidence,list) and p not in evidence:
            issues.append(prefix+'source_page_missing_from_top_level_citations')
    return raw,sorted(set(issues))

def skipped(raw,status,reason):
    return {'status':status,'reason':reason,'answer':copy.deepcopy(raw),
            'calculator_executed':False}

def postprocess(answer_text,case,assets,prepared=None):
    prepared=Path(prepared or ROOT/'prepared').resolve()
    supplied=[assets[k]['pdf_page_index'] for k in case['page_assets']]
    require(all(type(p) is int and p>=0 for p in supplied) and len(set(supplied))==len(supplied),
            'Invalid supplied-page identities')
    raw,issues=parse_schema(answer_text,supplied)
    trace=['parse_schema']
    output={'runner_version':5,'table_binding_version':2,'calculator_version':4,
            'raw_answer_text':answer_text,'raw_answer_text_sha256':digest(answer_text.encode('utf-8')),
            'raw_answer_record':copy.deepcopy(raw),'schema_issues':issues,
            'source_verified':False,'candidate_answer':None,'processing_trace':trace,
            'literal_screen':{'policy':'diagnostic_only; table geometry and normalized amount control the match','fields':[]},
            'table_binding':{'status':'not_attempted','bindings':[],'reasons':[],'source_verified':False}}
    def finish(status,problems,calculation):
        output['calculator_result']=calculation
        output['evidence_gate']={'release_status':status,'problems':problems,'source_verified':False,
                                 'raw_evidence_unchanged':True,
                                 'limits':'Scoped source-cell matching and registered arithmetic only; no certification of full-answer relevance, source entity or formula semantics.'}
        return output
    # Even a malformed ancillary field must not turn a declared abstention into an answer.
    if isinstance(raw,dict) and raw.get('abstain') is True:
        output['table_binding']['status']='abstained'
        trace.append('preserve_abstention_skip_calculator')
        return finish('abstained',issues,skipped(raw,'preserved_abstention','Original abstention retained; no calculator call'))
    if issues:
        trace.append('schema_hold_skip_calculator')
        return finish('held_for_review',['schema:'+p for p in issues],
                      skipped(raw,'skipped_schema_hold','Schema issues prevent evidence/calculator processing'))
    trace.append('source_asset_check')
    native={}
    for key in case['page_assets']:
        a=assets[key]
        require(a['doc_id']==case['doc_id'],'Cross-document source asset')
        path=(prepared/a['text']).resolve()
        require(prepared in path.parents,'Text asset escaped prepared root')
        data=path.read_bytes()
        require(digest(data)==a['text_sha256'],'Native source text changed')
        native[a['pdf_page_index']]=data.decode('utf-8')
    asset_issues=[]
    asset_ids={assets[k]['pdf_page_index']:k for k in case['page_assets']}
    for i,field in enumerate(raw['source_values']):
        p=field['pdf_page_index']
        if field.get('asset_id') is not None and field['asset_id']!=asset_ids[p]:
            asset_issues.append(f'field_{i}:asset_id_disagrees_with_page')
        output['literal_screen']['fields'].append({'field':i,'cited_page':p,
                    'numeric_literal_present':literal_present(native[p],field['value'])})
    if asset_issues:
        trace.append('asset_hold_skip_calculator')
        return finish('held_for_review',asset_issues,
                      skipped(raw,'skipped_evidence_hold','Source asset identity disagrees with citation'))
    spec=copy.deepcopy(read(ROOT/'calculation_registry.json')['specifications'].get(case['case_id']))
    metrics=read(ROOT/'table_roles.json')['roles'].get(case['case_id'])
    if spec:
        for role in spec['roles']:
            role['allowed_pages']=supplied
    layout=validate_layout_cache(read(ROOT/'fixtures/layout_pages.json'),assets)
    trace.append('table_binding_v2')
    binding=bind_answer(raw,spec,metrics,case['doc_id'],supplied,layout)
    output['table_binding']=binding
    problems=['table:'+r for r in binding['reasons']]
    if binding['status']=='table_cell_match':
        used={b['source_field_index'] for b in binding['bindings']}
        if used!=set(range(len(raw['source_values']))):
            problems.append('unbound_source_fields_require_review')
    if binding['status']!='table_cell_match' or problems:
        trace.append('evidence_hold_skip_calculator')
        return finish('held_for_review',problems,
                      skipped(raw,'skipped_evidence_hold','Table/source checks did not permit calculator processing'))
    trace.append('calculator_v4')
    calculation=calculate_v3(raw,spec)
    calculation['calculator_executed']=True
    if calculation['status']!='calculated':
        return finish('held_for_review',['calculation_unresolved:'+calculation['status']],calculation)
    require(calculation['answer']['source_values']==raw['source_values'],'Calculator changed source fields')
    require(calculation['answer']['evidence_pages']==raw['evidence_pages'],'Calculator changed citations')
    output['candidate_answer']=copy.deepcopy(calculation['answer'])
    return finish('table_cell_match_unverified',[],calculation)
