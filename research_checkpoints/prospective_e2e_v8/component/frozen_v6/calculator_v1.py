"""Deterministic arithmetic from model-extracted fields; no reference answers or network."""
import copy,re
from decimal import Decimal,localcontext,ROUND_HALF_UP
class InputRejected(ValueError):pass

def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)):raise InputRejected('Source value must be a numeric JSON value, not text/bool/null')
    result=Decimal(str(value))
    if not result.is_finite():raise InputRejected('Non-finite source value')
    return result

def unit_kind(value):
    s=re.sub(r'[^a-z%$]','',str(value).lower())
    if s in ['%','percent','percentage']:return 'percent'
    if s in ['usd','dollars','$']:return 'usd'
    for scale in ['million','billion']:
        if s in [scale,scale+'s','usd'+scale,'usd'+scale+'s',scale+'usd',scale+'susd']:
            return 'usd_'+scale
    if s in ['indexvalue','indexpoints','indexvalueusd','dollarsindex']:return 'index'
    raise InputRejected('Unknown or incompatible source unit: '+str(value))

def bind_role(values,role):
    found=[]
    for v in values:
        if not isinstance(v,dict):continue
        if str(v.get('year',''))!=str(role['year']):continue
        if not re.search(role['label_pattern'],str(v.get('label','')),re.I):continue
        found.append(v)
    if len(found)!=1:raise InputRejected('Expected one unambiguous field for '+role['name']+'; found '+str(len(found)))
    v=found[0];page=v.get('pdf_page_index')
    if isinstance(page,bool) or not isinstance(page,int) or page not in role['allowed_pages']:raise InputRejected('Missing or disallowed page reference for '+role['name'])
    if unit_kind(v.get('unit',''))!=role['unit_kind']:raise InputRejected('Source scale/unit mismatch for '+role['name'])
    x=number(v.get('value'))
    if role.get('nonnegative') and x<0:raise InputRejected('Negative input disallowed for '+role['name'])
    if role.get('percent_range') and not Decimal(0)<=x<=Decimal(100):raise InputRejected('Percentage outside allowed range')
    return x,{'name':role['name'],'value':str(x),'year':v['year'],'unit':v['unit'],'pdf_page_index':page,'label':v['label'],'currency_note':'Currency inferred from question for magnitude-only source unit.' if str(v['unit']).lower() in ['million','millions','billion','billions'] else None}

def repair(answer,spec):
    original=copy.deepcopy(answer)
    if not isinstance(answer,dict) or not isinstance(answer.get('abstain'),bool):return {'status':'declined','reason':'Missing/invalid abstention field','answer':original}
    if answer['abstain']:return {'status':'preserved_abstention','reason':'No inference of missing values; original abstention retained','answer':original}
    if spec is None:return {'status':'not_applicable','reason':'No calculator operation registered for this question','answer':original}
    if not isinstance(answer.get('source_values'),list):return {'status':'declined','reason':'Missing structured source values','answer':original}
    try:
        pairs=[bind_role(answer['source_values'],r) for r in spec['roles']];v={r['name']:x[0] for r,x in zip(spec['roles'],pairs)}
        with localcontext() as ctx:
            ctx.prec=50;op=spec['operation']
            if op=='signed_difference':raw=v['end']-v['start'];formula=f"{v['end']} - {v['start']}"
            elif op=='cumulative_return_percent':
                if v['start']<=0:raise InputRejected('Initial index must be positive')
                raw=(v['end']/v['start']-1)*100;formula=f"({v['end']} / {v['start']} - 1) * 100"
            elif op=='ratio_to_average':
                den=(v['start']+v['end'])/2
                if den<=0:raise InputRejected('Average denominator must be positive')
                raw=v['numerator']/den;formula=f"{v['numerator']} / (({v['start']} + {v['end']}) / 2)"
            elif op=='percentage_of':
                if v['denominator']<=0:raise InputRejected('Denominator must be positive')
                raw=v['numerator']/v['denominator']*100;formula=f"({v['numerator']} / {v['denominator']}) * 100"
            else:raise InputRejected('Operation not allowed')
            result=raw.quantize(Decimal(1).scaleb(-spec['decimal_places']),rounding=ROUND_HALF_UP)
        out=copy.deepcopy(answer);out.update(answer=int(result) if spec['decimal_places']==0 else float(result),unit=spec['output_unit'],explanation=f"Deterministic calculator: {formula} = {raw}; rounded HALF_UP to {spec['decimal_places']} decimals = {result} {spec['output_unit']}. Source values and references are unchanged.")
        return {'status':'calculated','reason':'Source fields passed role/year/unit/page checks; numeric truth was not independently verified by the calculator','bound_inputs':[x[1] for x in pairs],'operation':op,'formula':formula,'unrounded_result':str(raw),'rounded_result':str(result),'original_final_answer':answer.get('answer'),'numeric_answer_changed':not isinstance(answer.get('answer'),(int,float)) or isinstance(answer.get('answer'),bool) or number(answer['answer'])!=result,'answer':out}
    except (InputRejected,ArithmeticError) as e:return {'status':'declined','reason':str(e),'answer':original}
