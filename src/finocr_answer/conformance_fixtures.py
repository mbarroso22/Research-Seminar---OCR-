"""Handwritten fictional test responses, never generator inputs or measured answers."""
from copy import deepcopy
from .synthetic import cases


def pages(case_id):
    case=next(c for c in cases() if c['task_id']=='synthetic:'+case_id)
    return {p['page_id']:p['raw_text'] for p in case['pages']}


def quantity(case_id,identifier,value,*,unit='amount',currency='USD',scale='million',year='2031'):
    # Order matches the typed-quantity union transmitted to the converter.
    return {'unit':unit,'currency':currency,'scale':scale,'id':identifier,'name':identifier,
            'value':value,'fiscal_year':year,'source':{'page_id':0,'span':pages(case_id)[0]}}


def positives():
    result={}
    for name in ['signed','scale','margin','comparison','missing','capacity']:
        if name in {'missing','capacity'}:
            result[name]={'status':'insufficient_evidence','answer':'insufficient_evidence','claims':[],
                          'quantities':[],'calculation':None,'missing_information':['Current liabilities were not supplied.']}
            continue
        answer={'signed':'Operating cash flow was -12.5 USD million.',
                'scale':'Revenue was 1250 USD million.',
                'margin':'Gross margin was 25 percent, up 5 percentage points from 20 percent.',
                'comparison':'Operations supplied the most cash; profit declined because input costs increased.'}[name]
        result[name]={'status':'answered','answer':answer,
            'claims':[{'text':answer,'support':[{'page_id':0,'span':pages(name)[0]}]}],
            'quantities':[],'calculation':None,'missing_information':[]}
    result['signed']['quantities']=[quantity('signed','cash','-12.5')]
    result['scale']['quantities']=[quantity('scale','revenue','1.25',scale='billion'),quantity('scale','converted','1250')]
    result['scale']['calculation']={'operand_ids':['revenue'],'expression':'revenue*1000','result':'1250','unit':'USD million'}
    result['margin']['quantities']=[quantity('margin','revenue','240'),quantity('margin','cost','180'),
        quantity('margin','prior','20',unit='percent',currency='none',scale='unit',year='2030'),
        quantity('margin','current','25',unit='percent',currency='none',scale='unit'),
        quantity('margin','change','5',unit='percentage_points',currency='none',scale='unit')]
    result['margin']['calculation']={'operand_ids':['revenue','cost'],'expression':'(revenue-cost)/revenue*100','result':'25','unit':'percent'}
    result['comparison']['quantities']=[quantity('comparison','operations','40'),quantity('comparison','investing','-12'),quantity('comparison','financing','-9')]
    return result


def negatives():
    """One-defect mutations; expected facts never enter a prompt/schema envelope."""
    good=positives();out=[]
    def add(label,case,mutate):
        value=deepcopy(good[case]);mutate(value);out.append((label,case,value))
    add('wrong_dimension','signed',lambda r:r['quantities'][0].update(unit='percent'))
    add('bad_numeric_prefix','signed',lambda r:r['quantities'][0].update(value='value: -12.5'))
    add('wrong_scale','signed',lambda r:r['quantities'][0].update(scale='thousand'))
    add('wrong_year','signed',lambda r:r['quantities'][0].update(fiscal_year='2030'))
    add('wrong_sign','comparison',lambda r:r['quantities'][2].update(value='9'))
    add('nonliteral_source','margin',lambda r:r['quantities'][1]['source'].update(span='Cedar Works FY2031: cost of sales 180 USD million.'))
    add('outside_page','signed',lambda r:r['claims'][0]['support'][0].update(page_id=99))
    add('literal_only_formula','margin',lambda r:r['calculation'].update(expression='(240-180)/240*100'))
    add('undefined_operand','scale',lambda r:r['calculation']['operand_ids'].append('scale_factor'))
    add('unused_operand','scale',lambda r:r['calculation']['operand_ids'].append('converted'))
    add('wrong_arithmetic','margin',lambda r:r['calculation'].update(result='24'))
    add('missing_requested_change','margin',lambda r:r['quantities'].pop())
    add('missing_typed_conversion_result','scale',lambda r:r['quantities'].pop())
    add('answered_abstention_marker','signed',lambda r:r.update(answer='insufficient_evidence'))
    add('abstention_asserted_claim','capacity',lambda r:r['claims'].append({'text':'The ratio can be calculated.',
        'support':[{'page_id':0,'span':'Current liabilities were not supplied.'}]}))
    add('abstention_missing_facts','capacity',lambda r:r.update(missing_information=[]))
    add('answered_without_required_ratio','capacity',lambda r:r.update(status='answered',answer='No. Current liabilities were not supplied.',
        claims=[{'text':'The ratio cannot be calculated.','support':[{'page_id':0,'span':'Current liabilities were not supplied.'}]}],missing_information=[]))
    return out
