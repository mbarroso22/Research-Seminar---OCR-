"""Separate reference evaluation; not imported by generation/payload code."""
import argparse
from decimal import Decimal,localcontext,ROUND_HALF_UP
from fractions import Fraction
import json
from pathlib import Path
import re
from io_utils import read,write,require,digest
from run_pilot import ROOT,validate_bundle,eligible

def expected_answer(cid,reference,spec):
    if spec['operation']=='working_capital_sign':return 'Yes' if reference['expected_positive'] else 'No'
    f=Fraction(reference['reference_fraction'])
    with localcontext() as ctx:
        ctx.prec=60
        return (Decimal(f.numerator)/Decimal(f.denominator)).quantize(Decimal(1).scaleb(-spec['decimal_places']),rounding=ROUND_HALF_UP)

def final_correct(value,expected):
    if isinstance(expected,str):
        return isinstance(value,str) and re.match(r'^\s*'+expected+r'\b',value,re.I) is not None
    return type(value) in (int,float) and Decimal(str(value)).is_finite() and Decimal(str(value))==expected

def unit_correct(value,expected):
    key=re.sub('[^a-z]','',str(value).lower())
    aliases={'USD billions':{'usdbillions','billions','billionusd','billionsusd'},
             'USD millions':{'usdmillions','millions','millionusd','millionsusd'},
             'times':{'times','ratio','turns','x'},
             'percentage points':{'percentagepoints','percentagepoint','pp'},
             'yes/no':{'yesno','yesorno','qualitative',''}}
    return key in aliases[expected]

def independent_amount(value,unit):
    if type(value) not in (int,float):raise ValueError('Not numeric')
    v=Fraction(str(value));key=re.sub('[^a-z$]','',str(unit).lower())
    for stem,factor in [('thousand',Fraction(1,1000)),('million',Fraction(1)),('billion',Fraction(1000))]:
        if key in {stem,stem+'s','usd'+stem,'usd'+stem+'s',stem+'usd',stem+'susd',stem+'ofusd',stem+'sofusd',stem+'ofusdollars',stem+'sofusdollars'}:return v*factor
    if key in {'usd','dollars','$'}:return v/1000000
    raise ValueError('Unsupported unit')

def source_support(raw,reference,spec,supplied):
    if not isinstance(raw,dict) or raw.get('abstain') is True:return None,'not_answered'
    fields=raw.get('source_values')
    if not isinstance(fields,list):return False,'missing_fields'
    if len(fields)!=len(spec['roles']):return False,'extra_or_missing_source_fields'
    pending=False
    for role in spec['roles']:
        matches=[]
        for field in fields:
            if not isinstance(field,dict):continue
            year=re.fullmatch(r'(?:FY\s*|Fiscal\s*)?((?:19|20)\d{2})',str(field.get('year')),re.I)
            if year and int(year.group(1))==role['year'] and re.search(role['label_pattern'],str(field.get('label','')),re.I):matches.append(field)
        if len(matches)!=1:return False,'ambiguous_or_missing_role'
        field=matches[0];ref=reference['roles'][role['name']]
        try:amount_ok=independent_amount(field.get('value'),field.get('unit'))==Fraction(ref['amount_millions'])
        except (ValueError,ZeroDivisionError):amount_ok=False
        if not amount_ok:return False,'amount_or_unit_mismatch'
        p=field.get('pdf_page_index')
        if type(p) is not int or p not in supplied:return False,'unsupplied_citation'
        if p not in ref['source_pages']:pending=True
    if pending:return None,'alternative_supplied_page_requires_review'
    return True,'registered_reference_operands_supported'

def evaluate(run):
    cases,assets=validate_bundle();refs=read(ROOT/'evaluation/references.json');specs=read(ROOT/'calculation_registry.json')['specifications']
    policy=read(run/'policy.json')
    require(policy['study_lock_sha256']==digest((ROOT/'study_lock.json').read_bytes()),'Result study lock mismatch')
    rows=[]
    for c in cases:
        folder=run/(c['case_id']+'-'+c['arm']);attempts=list(folder.glob('attempt-*/result.json'))
        require(len(attempts)<=1,'Multiple attempts need explicit accounting')
        row={'case_id':c['case_id'],'arm':c['arm'],'planned':True,'attempted':bool(attempts),'completed':False,
             'raw_answered':False,'raw_abstained':False,'raw_final_correct':False,'candidate_present':False,
             'raw_final_unit_correct':False,'candidate_final_unit_correct':False,
             'candidate_final_correct':False,'reference_source_support':None,'source_review_status':'not_completed',
             'candidate_unsupported_by_automatic_reference_check':False,'candidate_source_review_pending':False,
             'source_complete_input_held':False,'gate_blocked_control':False,'source_verified':False,'semantic_review':'pending'}
        if attempts:
            m=read(attempts[0]);row.update(status=m['status'],estimated_usd=m.get('estimated_usd'),usage=m.get('usage'),wall_seconds=m.get('wall_seconds'))
            row['completed']=eligible(m)
            ppfile=attempts[0].parent/'postprocessed.json'
            if row['completed'] and ppfile.exists():
                p=read(ppfile);raw=p['raw_answer_record'];candidate=p['candidate_answer'];expected=expected_answer(c['case_id'],refs[c['case_id']],specs[c['case_id']])
                row.update(release_status=p['evidence_gate']['release_status'],calculator_status=p['calculator_result']['status'],
                           raw_abstained=raw.get('abstain') is True,raw_answered=raw.get('abstain') is False,
                           candidate_present=candidate is not None)
                if c['arm']=='empty_context':
                    row['gate_blocked_control']=candidate is None
                    row['source_review_status']='artificial_empty_context_control'
                else:
                    support,reason=source_support(raw,refs[c['case_id']],specs[c['case_id']],{assets[k]['pdf_page_index'] for k in c['page_assets']})
                    row.update(raw_final_correct=not row['raw_abstained'] and final_correct(raw.get('answer'),expected),
                               raw_final_unit_correct=unit_correct(raw.get('unit'),specs[c['case_id']]['output_unit']),
                               reference_source_support=support,source_review_status=reason,
                               source_complete_input_held=support is True and p['evidence_gate']['release_status']=='held_for_review')
                    if candidate is not None:
                        correct=final_correct(candidate.get('answer'),expected)
                        row.update(candidate_final_correct=correct,
                                   candidate_final_unit_correct=unit_correct(candidate.get('unit'),specs[c['case_id']]['output_unit']),
                                   candidate_unsupported_by_automatic_reference_check=(not correct or support is False),
                                   candidate_source_review_pending=support is None)
        rows.append(row)
    summaries=[]
    for arm in ['retrieved_text','retrieved_image','oracle_image','empty_context']:
        rr=[r for r in rows if r['arm']==arm]
        q={'arm':arm,'planned':len(rr),'attempted':sum(r['attempted'] for r in rr),'completed':sum(r['completed'] for r in rr),
           'results_complete':all(r['completed'] for r in rr),'candidate_coverage_all_planned':sum(r['candidate_present'] for r in rr)/len(rr),
           'candidate_count':sum(r['candidate_present'] for r in rr),
           'estimated_generation_usd':sum(r.get('estimated_usd') or 0 for r in rr),
           'input_tokens':sum((r.get('usage') or {}).get('prompt_tokens',0) for r in rr),
           'output_tokens':sum((r.get('usage') or {}).get('completion_tokens',0) for r in rr)}
        if arm=='empty_context':q.update(model_abstentions=sum(r['raw_abstained'] for r in rr),gate_blocked_controls=sum(r['gate_blocked_control'] for r in rr))
        else:q.update(raw_final_correct=sum(r['raw_final_correct'] for r in rr),raw_numeric_accuracy_all_planned=sum(r['raw_final_correct'] for r in rr)/len(rr),
                      raw_answer_and_unit_correct=sum(r['raw_final_correct'] and r['raw_final_unit_correct'] for r in rr),
                      candidate_final_correct=sum(r['candidate_final_correct'] for r in rr),
                      candidate_numeric_accuracy_all_planned=sum(r['candidate_final_correct'] for r in rr)/len(rr),
                      source_complete_inputs_held=sum(r['source_complete_input_held'] for r in rr),
                      unsupported_candidates=sum(r['candidate_unsupported_by_automatic_reference_check'] for r in rr),
                      candidate_source_review_pending=sum(r['candidate_source_review_pending'] for r in rr))
        summaries.append(q)
    result={'scope':'Additional-question locked generation pilot after development preflight; reused project sources and prior text-model tasks. Oracle and empty context diagnostic only.',
            'results_complete':all(r['completed'] for r in rows),'planned_conditions':16,'completed_conditions':sum(r['completed'] for r in rows),
            'generation_cost_estimated_usd':sum(q['estimated_generation_usd'] for q in summaries),'summaries':summaries,
            'manual_review':'Automatic numeric/reference checks only. Alternative supplied citations, entity relevance, qualitative applicability and free-form explanation require review. source_verified remains false.',
            'independence':'4 questions from the previously used benchmark pool, correlated arms, no repeats; descriptive prospective workflow pilot only. Missing/capped/error attempts remain in planned denominators.'}
    write(run/'evaluation/summary.json',result);write(run/'evaluation/records.json',rows)
    print(json.dumps(result,indent=2))
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--latest-from',required=True,type=Path);args=ap.parse_args()
    base=args.latest_from.resolve();name=(base/'latest_run.txt').read_text(encoding='utf-8').strip();run=(base/name).resolve()
    require(base in run.parents,'Invalid run pointer');evaluate(run)

if __name__=='__main__':main()
