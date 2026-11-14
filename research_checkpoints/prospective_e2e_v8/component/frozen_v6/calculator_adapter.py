"""Preserved calculator-v3 alias adapter; invoked only after evidence match."""
import copy,re
import calculator_v2

UNIT_ALIASES={'million of usd':'USD millions','millions of usd':'USD millions',
              'million of us dollars':'USD millions','millions of us dollars':'USD millions'}


def calculate_v3(answer,spec):
    adapted=copy.deepcopy(answer);aliases=[]
    if isinstance(adapted,dict) and isinstance(adapted.get('source_values'),list) and spec is not None:
        for i,field in enumerate(adapted['source_values']):
            if not isinstance(field,dict):continue
            unit=re.sub(r'\s+',' ',str(field.get('unit','')).strip().lower())
            if unit in UNIT_ALIASES:
                aliases.append({'field':i,'original_unit':field['unit'],'normalized_unit':UNIT_ALIASES[unit]})
                field['unit']=UNIT_ALIASES[unit]
    result=calculator_v2.repair(adapted,spec)
    if isinstance(result.get('answer'),dict) and isinstance(answer,dict):
        result['answer']['source_values']=copy.deepcopy(answer.get('source_values'))
    if result['status']=='declined':result['answer']=copy.deepcopy(answer)
    result['candidate_calculator_version']=3;result['unit_alias_normalizations']=aliases
    return result
