"""Strict, source-independent response mechanics plus fixed synthetic fact checks.

This is not a general entailment detector. Semantic/formula review remains explicit.
No repair, number extraction from malformed strings, or unit rewriting is performed.
"""
from __future__ import annotations
import ast
import keyword
import re
from decimal import Decimal
from .contract import CONTRACT_VERSION, schema_issues
from .evaluator import arithmetic, citation_check, decimal_string, quantity_check


def validate_response(value: dict, pages: dict[int,str]) -> dict:
    issues = schema_issues(value)
    schema_pass = not issues
    def issue(code,path,message): issues.append({'code':code,'path':path,'message':message})
    if not isinstance(value,dict):
        return {'contract_version':CONTRACT_VERSION,'schema':False,'mechanical_pass':False,'issues':issues,
                'semantic_support':'pending_manual_review','fully_supported_pass':False}
    quantities=value.get('quantities',[])
    if not isinstance(quantities,list): quantities=[]
    ids={}; parsed={}
    for index,q in enumerate(quantities):
        if not isinstance(q,dict): continue
        path=f'quantities[{index}]'; identifier=q.get('id')
        if not isinstance(identifier,str) or not identifier.isidentifier() or keyword.iskeyword(identifier):
            issue('invalid_identifier',path+'.id','Quantity IDs must be usable arithmetic names')
        elif identifier in ids: issue('duplicate_quantity_id',path+'.id',identifier)
        else: ids[identifier]=q
        try:
            if not isinstance(q.get('value'),str): raise ValueError('Expected string')
            parsed[identifier]=decimal_string(q['value'])
        except (ValueError,TypeError): issue('invalid_numeric_value',path+'.value','Not a signed decimal; no value-prefix repair')
        unit,currency,scale=q.get('unit'),q.get('currency'),q.get('scale')
        if unit=='amount' and currency!='USD': issue('currency_dimension',path,'Amounts require the fictional-source currency USD')
        if unit in ('percent','percentage_points','ratio') and (currency!='none' or scale!='unit'):
            issue('unit_scale_dimension',path,'Dimensionless quantities require currency none and scale unit')
        if not citation_check(q.get('source',{}) if isinstance(q.get('source'),dict) else {},pages):
            issue('quantity_citation',path+'.source','Included zero-based page and nonempty literal span required')
    claims=value.get('claims',[])
    if isinstance(claims,list):
        for index,claim in enumerate(claims):
            if not isinstance(claim,dict): continue
            for pointer in claim.get('support',[]) if isinstance(claim.get('support'),list) else []:
                if not isinstance(pointer,dict) or not citation_check(pointer,pages):
                    issue('claim_citation',f'claims[{index}]','Invalid page or literal span')
    if value.get('status')=='insufficient_evidence':
        if value.get('claims') or value.get('quantities') or value.get('calculation') is not None or value.get('answer')!='insufficient_evidence':
            issue('abstention_conflict','status','An abstention must not assert an answer, claim, quantity or calculation')
        missing=value.get('missing_information')
        if not isinstance(missing,list) or not missing or any(not isinstance(s,str) or not s.strip() for s in missing):
            issue('missing_abstention_facts','missing_information','Identify the missing facts with nonblank text')
    if value.get('status')=='answered':
        answer=value.get('answer')
        if isinstance(answer,str) and answer.strip().casefold()=='insufficient_evidence':
            issue('abstention_conflict','answer','An answered response cannot use the reserved abstention answer marker')
        if not isinstance(answer,str) or not answer.strip():
            issue('blank_answer','answer','An answered response requires a substantive answer')
    calc=value.get('calculation')
    calculation=None
    if isinstance(calc,dict):
        operands=calc.get('operand_ids',[]); expression=calc.get('expression')
        if not isinstance(operands,list) or any(not isinstance(o,str) for o in operands): operands=[]
        if len(set(operands))!=len(operands): issue('duplicate_operand','calculation.operand_ids','Operand IDs must be unique')
        unknown=[o for o in operands if o not in ids]
        if unknown: issue('undefined_operand','calculation.operand_ids',str(unknown))
        try:
            if not isinstance(expression,str) or len(expression)>256: raise ValueError('Invalid expression length')
            tree=ast.parse(expression,mode='eval')
            references={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
            if references != set(operands): issue('operand_expression_mismatch','calculation.expression','Expression names must equal the declared operands; literal-only substitution is forbidden')
            if not references: issue('unlinked_calculation','calculation.expression','At least one quantity operand must be used')
            if references-set(ids): issue('undefined_expression_name','calculation.expression',str(sorted(references-set(ids))))
            result=arithmetic(expression,{o:parsed[o] for o in operands})
            claimed=decimal_string(calc['result'])
            calculation={'recomputed':str(result),'declared':str(claimed),'exact_match':result==claimed}
            if result!=claimed: issue('arithmetic_mismatch','calculation.result','Declared result differs from independently recomputed arithmetic')
            # The instruction requires each requested result as a typed quantity,
            # not only in the calculation object. Compare without unit/value repair.
            unit=calc.get('unit')
            amount_scales={'USD':'unit','USD thousand':'thousand','USD million':'million','USD billion':'billion'}
            expected_dimension=('amount','USD',amount_scales[unit]) if unit in amount_scales else (unit,'none','unit')
            matched=False
            for q in quantities:
                if not isinstance(q,dict):continue
                try:
                    matched=matched or (decimal_string(q['value'])==claimed and
                        (q.get('unit'),q.get('currency'),q.get('scale'))==expected_dimension)
                except (KeyError,TypeError,ValueError):pass
            if not matched:
                issue('calculation_result_quantity','calculation.result','Record the result as a quantity with the same value and dimensions')
        except (KeyError,ValueError,TypeError,SyntaxError,ArithmeticError) as exc:
            issue('invalid_calculation','calculation',f'{type(exc).__name__}: {exc}')
    return {'contract_version':CONTRACT_VERSION,'schema':schema_pass,'mechanical_pass':not issues,'issues':issues,'calculation':calculation,
            'semantic_support':'pending_manual_review','financial_formula':'pending_manual_review','fully_supported_pass':False}


# Facts are synthetic evaluator data, never serialized into a model request.
def _facts(case_id):
    def q(value,unit='amount',year='2031',currency='USD',scale='million'):
        return {'value':value,'unit':unit,'fiscal_year':year,'currency':currency,'scale':scale,'quantum':'0.01'}
    return {
        'signed':[q('-12.5')], 'scale':[q('1250')],
        'margin':[q('240'),q('180'),q('20','percent','2030','none','unit'),q('25','percent','2031','none','unit'),q('5','percentage_points','2031','none','unit'),q('60')],
        'comparison':[q('40'),q('-12'),q('-9')], 'missing':[], 'capacity':[]}[case_id]


def functional_checks(value: dict,case_id: str,pages:dict[int,str]) -> dict:
    report=validate_response(value,pages)
    issues=report['issues']
    if not isinstance(value,dict):return {**report,'expected_status':False,'mechanical_pass':False}
    def issue(code,message):issues.append({'code':code,'path':'synthetic:'+case_id,'message':message})
    report['expected_status']=value.get('status')==('insufficient_evidence' if case_id in {'missing','capacity'} else 'answered') if isinstance(value,dict) else False
    if not report['expected_status']: issue('expected_status','Status disagrees with fictional context')
    facts=_facts(case_id)
    quantities=value.get('quantities',[]) if isinstance(value,dict) else []
    quantities=quantities if isinstance(quantities,list) else []
    required=len(facts) if case_id in {'signed','scale','comparison'} else 5 if case_id=='margin' else 0
    for index,fact in enumerate(facts[:required]):
        found=any(isinstance(q,dict) and quantity_check(q,fact)['pass'] for q in quantities)
        report[f'quantity_{index}']=found
        if not found:issue('required_quantity',f'Missing or incorrect required fact {index}')
    for index,q in enumerate(quantities):
        if not isinstance(q,dict):continue
        if not any(quantity_check(q,f)['pass'] for f in facts):issue('unsupported_quantity',f'Quantity {index} does not match any permitted source/derived synthetic fact')
        # Associate comparison figures with the named activity independently of syntax.
        if case_id=='comparison':
            name=(str(q.get('name',''))+' '+str(q.get('id',''))).lower()
            role=next((i for i,words in enumerate([('operat',),('invest',),('financ',)]) if any(w in name for w in words)),None)
            if role is not None and not quantity_check(q,facts[role])['pass']:
                issue('activity_value_or_sign',f'Quantity {index} has wrong signed figure for its named activity')
    if isinstance(value,dict) and isinstance(value.get('calculation'),dict) and case_id in {'signed','scale','margin'}:
        expected_result,expected_unit={'signed':(Decimal('-12.5'),'USD million'),'scale':(Decimal('1250'),'USD million'),'margin':(Decimal('25'),'percent')}[case_id]
        try:
            if decimal_string(value['calculation']['result'])!=expected_result or value['calculation']['unit']!=expected_unit:
                issue('expected_calculation_result','Calculation result/unit differs from the requested fictional quantity')
        except (KeyError,TypeError,ValueError):issue('expected_calculation_result','Invalid result/unit')
    if case_id=='scale' and value.get('calculation') is None:
        issue('missing_conversion_calculation','Record the source-linked conversion to USD million')
    if case_id in {'missing','capacity'}:
        report['explicit_missing_facts']=bool(value.get('missing_information')) if isinstance(value,dict) else False
    if case_id=='comparison':
        if value.get('calculation') is not None: issue('unrequested_calculation','Selection/interpretation task requires null calculation, not an invented cash-flow total')
        report['operations_and_profit_decline']='pending_manual_review'
    if case_id=='margin':
        result=report.get('calculation')
        report['arithmetic_25_percent']=bool(result and result['exact_match'] and Decimal(result['recomputed'])==25 and value['calculation']['unit']=='percent')
        if not report['arithmetic_25_percent']: issue('gross_margin_calculation','Source-linked gross-margin calculation must independently yield 25 percent')
        report['five_percentage_point_change']='pending_manual_review'
    report['citation_structure']=not any(i['code'] in {'quantity_citation','claim_citation'} for i in issues)
    report['mechanical_pass']=not issues
    return report
