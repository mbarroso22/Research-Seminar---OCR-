"""Offline-only v3 adapter: schema -> exact source binding -> arithmetic.

The baseline parser/calculator are preserved. New normalizations are private
calculator inputs with explicit traces; original source fields never change.
"""
import copy
import json
from pathlib import Path

from legacy import BASE, binding_v2, pipeline_v6, calculate_v4
from binding_v3 import bind_answer


def calculate_bound(answer,spec,binding):
    if binding.get('status')!='table_cell_match':
        raise ValueError('Calculator requires complete source binding')
    fields=answer['source_values']
    if {b['source_field_index'] for b in binding['bindings']}!=set(range(len(fields))):
        raise ValueError('Supplemental or unbound fields forbid calculation')
    adapted=copy.deepcopy(answer);trace=[]
    for b in binding['bindings']:
        i=b['source_field_index'];field=adapted['source_values'][i]
        # The unchanged calculators accept Decimal inputs through their legacy
        # number routine. Keep exact normalized amounts, never binary rounding.
        from decimal import Decimal
        field.update(value=Decimal(b['model_amount_millions']),unit='USD millions',year=b['expected_year'])
        trace.append({'source_field_index':i,'original_value':fields[i]['value'],'original_unit':fields[i]['unit'],
                      'normalized_value_usd_millions':b['model_amount_millions'],'normalization':b['normalization']})
    result=calculate_v4(adapted,copy.deepcopy(spec))
    result['binding_adapter_version']=3;result['bound_input_normalizations']=trace
    if result.get('status')=='calculated':
        result['answer']['source_values']=copy.deepcopy(answer['source_values'])
        result['answer']['evidence_pages']=copy.deepcopy(answer['evidence_pages'])
    else:result['answer']=copy.deepcopy(answer)
    result['calculator_executed']=True
    return result


def postprocess(answer_text,case,assets,document_context,role_contexts=None):
    supplied=[assets[k]['pdf_page_index'] for k in case['page_assets']]
    raw,issues=pipeline_v6.parse_schema(answer_text,supplied)
    result={'offline_pipeline_version':3,'table_binding_version':3,'calculator_version':4,
            'raw_answer_text':answer_text,'raw_answer_text_sha256':pipeline_v6.digest(answer_text.encode('utf-8')),
            'raw_answer_record':copy.deepcopy(raw),'schema_issues':issues,'source_verified':False,
            'candidate_answer':None,'processing_trace':['baseline_parse_schema'],'table_binding':None}
    def finish(status,reasons,calculation=None):
        result['evidence_gate']={'release_status':status,'problems':reasons,'source_verified':False,'raw_evidence_unchanged':True}
        result['calculator_result']=calculation or {'status':'preserved_abstention' if status=='abstained' else 'skipped_schema_hold' if issues else 'skipped_evidence_hold',
                                                   'calculator_executed':False,'answer':copy.deepcopy(raw)}
        return result
    if isinstance(raw,dict) and raw.get('abstain') is True:
        return finish('abstained',issues)
    if issues:return finish('held_for_review',['schema:'+s for s in issues])
    prepared=BASE/'prepared'
    for key in case['page_assets']:
        a=assets[key];path=(prepared/a['text']).resolve()
        if a['doc_id']!=case['doc_id'] or prepared.resolve() not in path.parents:
            raise ValueError('Cross-document or escaped source asset')
        if pipeline_v6.digest(path.read_bytes())!=a['text_sha256']:
            raise ValueError('Source text fingerprint changed')
    spec=copy.deepcopy(json.loads((BASE/'calculation_registry.json').read_text(encoding='utf-8'))['specifications'][case['case_id']])
    metrics=json.loads((BASE/'table_roles.json').read_text(encoding='utf-8'))['roles'][case['case_id']]
    for role in spec['roles']:role['allowed_pages']=supplied
    cache=binding_v2.validate_layout_cache(json.loads((BASE/'fixtures/layout_pages.json').read_text(encoding='utf-8')),assets)
    result['processing_trace'].append('binding_v3')
    binding=bind_answer(raw,spec,metrics,case['doc_id'],supplied,cache,document_context,role_contexts)
    result['table_binding']=binding
    if binding['status']!='table_cell_match':return finish('held_for_review',['table:'+r for r in binding['reasons']])
    result['processing_trace'].append('calculator_v4_with_bound_input_adapter_v3')
    calculation=calculate_bound(raw,spec,binding)
    if calculation['status']!='calculated':return finish('held_for_review',['calculator_declined'],calculation)
    if calculation['answer']['source_values']!=raw['source_values'] or calculation['answer']['evidence_pages']!=raw['evidence_pages']:
        raise ValueError('Calculator changed original evidence')
    result['candidate_answer']=copy.deepcopy(calculation['answer'])
    return finish('table_cell_match_unverified',[],calculation)
