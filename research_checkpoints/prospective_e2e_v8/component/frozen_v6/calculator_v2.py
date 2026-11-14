"""Version2 adapter: bounded years/USD scales plus a direct ratio operation.

Original engine remains byte-identical. Source records are preserved unchanged.
This is a new candidate, not retroactive modification of the completed study.
"""
import copy,re
from decimal import Decimal,localcontext,ROUND_HALF_UP
import calculator_v1 as core

def normalize_year(value):
    if type(value) is int and 1900<=value<=2099:return value
    if isinstance(value,str):
        match=re.fullmatch(r'(?:FY\s*|Fiscal\s*)?((?:19|20)\d{2})',value.strip(),re.I)
        if match:return int(match[1])
    raise core.InputRejected('Unambiguous calendar/fiscal year required; ranges and periods unsupported')

def repair(answer,spec):
    if not isinstance(answer,dict) or spec is None or answer.get('abstain') is not False:
        return core.repair(answer,spec)
    original=copy.deepcopy(answer);adapted=copy.deepcopy(answer);changes=[]
    if not isinstance(adapted.get('source_values'),list):return core.repair(answer,spec)
    try:
        for i,v in enumerate(adapted['source_values']):
            if not isinstance(v,dict):raise core.InputRejected('Malformed source field')
            old=v.get('year');year=normalize_year(old);v['year']=year
            if type(old) is not int or old!=year:changes.append({'field':i,'kind':'year','original':old,'normalized':year})
            unit=re.sub(r'[^a-z%$]','',str(v.get('unit','')).lower())
            scale=None
            if unit in ['thousand','thousands','usdthousand','usdthousands','thousandusd','thousandsusd']:scale=Decimal('0.001')
            elif unit in ['usd','dollars','$']:scale=Decimal('0.000001')
            elif unit in ['billion','billions','usdbillion','usdbillions','billionusd','billionsusd']:scale=Decimal('1000')
            if scale is not None:
                with localcontext() as ctx:ctx.prec=50;value=core.number(v.get('value'))*scale
                changes.append({'field':i,'kind':'USD_scale','original_unit':v['unit'],'original_value':v['value'],'normalized_unit':'USD millions','normalized_value':str(value),'note':'Magnitude-only currencies inferred only from task registry USD roles.'})
                v.update(value=value,unit='USD millions')
        if spec['operation']=='ratio':
            pairs=[core.bind_role(adapted['source_values'],r) for r in spec['roles']]
            values={r['name']:x[0] for r,x in zip(spec['roles'],pairs)}
            with localcontext() as ctx:
                ctx.prec=50
                if values['denominator']<=0:raise core.InputRejected('Denominator must be positive')
                raw=values['numerator']/values['denominator'];rounded=raw.quantize(Decimal(1).scaleb(-spec['decimal_places']),rounding=ROUND_HALF_UP)
            out=copy.deepcopy(adapted);out.update(answer=float(rounded),unit=spec['output_unit'],explanation=f"Deterministic calculator: {values['numerator']} / {values['denominator']} = {raw}; HALF_UP to {spec['decimal_places']} decimals = {rounded}.")
            result={'status':'calculated','reason':'Role/year/unit/page checks passed; numeric truth requires source review','bound_inputs':[x[1] for x in pairs],'operation':'ratio','unrounded_result':str(raw),'rounded_result':str(rounded),'answer':out}
        else:result=core.repair(adapted,spec)
    except (core.InputRejected,ArithmeticError) as e:return {'status':'declined','reason':str(e),'answer':original,'adapter_version':2}
    result['adapter_version']=2;result['normalizations']=changes
    # Internal normalization never replaces the raw evidence fields.
    if isinstance(result.get('answer'),dict):result['answer']['source_values']=copy.deepcopy(original['source_values'])
    if result['status']=='declined':result['answer']=original
    return result
