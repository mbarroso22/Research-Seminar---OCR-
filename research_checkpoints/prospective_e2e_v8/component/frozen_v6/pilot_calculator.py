"""Calculator v4: bounded new operations; legacy operations use unchanged v3."""
import copy
from decimal import Decimal,localcontext,ROUND_HALF_UP
from calculator_adapter import calculate_v3
from calculator_v2 import normalize_year
from calculator_v1 import bind_role,InputRejected
from table_binding import to_millions

NEW_OPERATIONS={'extract_amount','margin_delta_pp','working_capital_sign'}

def calculate_v4(answer,spec):
    if spec is None or spec.get('operation') not in NEW_OPERATIONS:
        return calculate_v3(answer,spec)
    original=copy.deepcopy(answer)
    if not isinstance(answer,dict) or answer.get('abstain') is not False:
        return {'status':'declined','answer':original,'reason':'Non-abstaining structured answer required'}
    adapted=copy.deepcopy(answer)
    try:
        for field in adapted['source_values']:
            field['year']=normalize_year(field['year'])
            field['value']=to_millions(field['value'],field['unit'])
            field['unit']='USD millions'
        pairs=[bind_role(adapted['source_values'],role) for role in spec['roles']]
        values={role['name']:pair[0] for role,pair in zip(spec['roles'],pairs)}
        op=spec['operation']
        with localcontext() as ctx:
            ctx.prec=50
            if op=='extract_amount':
                divisor=Decimal(str(spec['output_divisor_millions']))
                if divisor not in {Decimal(1),Decimal(1000)}:raise InputRejected('Unsupported output scale')
                raw=values['value']/divisor
                formula=f"{values['value']} / {divisor}"
            elif op=='margin_delta_pp':
                if values['revenue_start']<=0 or values['revenue_end']<=0:raise InputRejected('Revenue denominator must be positive')
                raw=(values['income_end']/values['revenue_end']-values['income_start']/values['revenue_start'])*100
                formula=f"({values['income_end']} / {values['revenue_end']} - {values['income_start']} / {values['revenue_start']}) * 100"
            else:
                raw=values['assets']-values['liabilities']
                formula=f"{values['assets']} - {values['liabilities']}"
            rounded=raw.quantize(Decimal(1).scaleb(-spec['decimal_places']),rounding=ROUND_HALF_UP)
        result=copy.deepcopy(original)
        if op=='working_capital_sign':
            result.update(answer='Yes' if raw>0 else 'No',unit='yes/no',
                          explanation=f"Deterministic calculator: current assets minus current liabilities = {formula} = {raw} USD millions; positive working capital: {'Yes' if raw>0 else 'No'}. Applicability context requires review.")
        else:
            result.update(answer=float(rounded),unit=spec['output_unit'],
                          explanation=f"Deterministic calculator: {formula} = {raw}; HALF_UP to {spec['decimal_places']} decimals = {rounded} {spec['output_unit']}. Source fields and citations preserved.")
        return {'status':'calculated','reason':'Registered arithmetic only; source/formula truth remains subject to review',
                'answer':result,'operation':op,'formula':formula,'bound_inputs':[p[1] for p in pairs],
                'unrounded_result':str(raw),'rounded_result':str(rounded),'pilot_calculator_version':4}
    except (ValueError,ArithmeticError,KeyError,TypeError) as exc:
        return {'status':'declined','reason':type(exc).__name__+': '+str(exc),'answer':original,'pilot_calculator_version':4}
