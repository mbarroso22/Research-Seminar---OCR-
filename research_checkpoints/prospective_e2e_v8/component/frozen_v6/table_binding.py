"""Version 2: conservative matching for supported annual financial tables.

Uses PDF words, not grading numbers. No network, generated formulas or silent
citation correction. Ambiguous/missing row, period, scale or cell yields a hold.
"""
import re,copy
from decimal import Decimal,InvalidOperation
from calculator_v2 import normalize_year

METRICS={
 'net_revenues':[r'^(?:total )?net revenues$',r'^revenues$',r'^total net revenue$'],
 'ppne':[r'^property and equipment net$',r'^property plant and equipment net$'],
 'operating_income':[r'^operating income$',r'^operating income loss$'],
 'cogs':[r'^cost of goods sold$',r'^cost of products sold$',r'^cost of sales$'],
 'net_operating_revenues':[r'^net operating revenues$'],
 'current_assets':[r'^total current assets$'],
 'current_liabilities':[r'^total current liabilities$'],
 'inventory':[r'^inventories(?: net)?$']}

def norm(s):return re.sub(r'[^a-z0-9]+',' ',s.lower().replace('&',' and ')).strip()
def bbox(words):return [min(w[0] for w in words),min(w[1] for w in words),max(w[2] for w in words),max(w[3] for w in words)]
def parse_number(s):
    s=s.strip().replace(',','').replace('$','').replace('−','-')
    if not re.fullmatch(r'\(?[-+]?\d+(?:\.\d+)?\)?',s):return None
    try:return Decimal(s.strip('()'))*(-1 if s.startswith('(') and s.endswith(')') else 1)
    except InvalidOperation:return None
def rows_from_words(words,tolerance=2.2):
    rows=[]
    for w in sorted(words,key=lambda w:((w[1]+w[3])/2,w[0])):
        y=(w[1]+w[3])/2
        if not rows or abs(y-rows[-1]['y'])>tolerance:rows.append({'y':y,'words':[]})
        rows[-1]['words'].append(w)
    for r in rows:
        r['words'].sort(key=lambda w:w[0]);r['text']=' '.join(w[4] for w in r['words'])
    return rows

HEADER_WORDS=set('at as of for the year years ended fiscal in amounts millions thousands billions except per share data par value unaudited january february march april may june july august september october november december'.split())

def validate_layout_cache(layout,assets):
    import math
    cache={}
    for p in layout:
        key=(p['doc_id'],p['pdf_page_index']);a=assets.get(p['asset_id'])
        if key in cache or a is None:raise ValueError('Duplicate or unknown layout asset')
        if type(p['pdf_page_index']) is not int or p['doc_id']!=a['doc_id'] or p['pdf_page_index']!=a['pdf_page_index'] or p['document_sha256']!=a['document_sha256']:raise ValueError('Layout/PDF identity mismatch')
        if not all(type(p[k]) in (int,float) and math.isfinite(p[k]) and p[k]>0 for k in ['width','height']):raise ValueError('Invalid page geometry')
        for w in p['words']:
            if len(w)!=5 or not isinstance(w[4],str) or not all(type(x) in (int,float) and math.isfinite(x) for x in w[:4]) or w[0]>w[2] or w[1]>w[3]:raise ValueError('Invalid word geometry')
        cache[key]=p
    return cache

def extract_cells(page,metric):
    if page.get('rotation',0)!=0:return []
    rows=rows_from_words(page['words']);width=page['width'];found=[]
    for ri,row in enumerate(rows):
        # Recognize a period header using standalone years in the numeric half.
        headers=[]
        for h in rows[:ri]:
            years=[w for w in h['words'] if re.fullmatch(r'(?:19|20)\d{2}',w[4]) and w[0]>width*.5]
            header_tokens=[t for t in norm(h['text']).split() if not t.isdigit()]
            # Only permit extra unit-clause vocabulary when an explicit scale
            # statement occurs on this same line. Do not whitelist general prose.
            has_scale_clause=bool(re.search(r'\bin\s+(?:thousands|millions|billions)\b',h['text'],re.I))
            allowed=HEADER_WORDS | ({'dollars','amount','and'} if has_scale_clause else set())
            if len(years)>=2 and len({w[4] for w in years})==len(years) and all(t in allowed for t in header_tokens):
                headers.append((h,[(int(w[4]),(w[0]+w[2])/2,w) for w in years],'year_columns'))
        mode=None
        if headers:
            h,columns,mode=headers[-1]
        # Single-year consolidating table: select the expressly Consolidated
        # column, never Subsidiary Issuer or Non-Guarantor subsidiary amounts.
        consolidating=[h for h in rows[:ri] if all(t in h['text'].lower() for t in ['parent','subsidiary','eliminations']) and any(w[4]=='Consolidated' for w in h['words'])]
        if consolidating and (not headers or consolidating[-1]['y']>h['y']):
            ch=consolidating[-1];dates=[d for d in rows if d['y']<ch['y'] and ch['y']-d['y']<100 and re.search(r'for the year ended',d['text'],re.I)]
            if not dates:continue
            yy=re.findall(r'\b(?:19|20)\d{2}\b',dates[-1]['text'])
            if len(yy)!=1:continue
            cw=[w for w in ch['words'] if w[4]=='Consolidated']
            if len(cw)!=1:continue
            h=dates[-1];columns=[(int(yy[0]),(cw[0][0]+cw[0][2])/2,cw[0])];mode='consolidated_single_year'
        if mode is None:continue
        if mode=='year_columns':
            gap=min(columns[j+1][1]-columns[j][1] for j in range(len(columns)-1));left=columns[0][1]-gap*.48;distance=gap*.48
        else:left=width*.40;distance=35
        label_words=[w for w in row['words'] if w[2]<left]
        label=norm(' '.join(w[4] for w in label_words))
        if not any(re.fullmatch(p,label) for p in METRICS[metric]):continue
        unit_rows=[u for u in rows if abs(u['y']-h['y'])<80 and u['y']<=row['y'] and re.search(r'\bin\s+(?:thousands|millions|billions)\b',u['text'],re.I)]
        units={re.search(r'\bin\s+(thousands|millions|billions)\b',u['text'],re.I).group(1).lower() for u in unit_rows}
        if len(units)!=1:continue
        unit=next(iter(units));unit_row=min(unit_rows,key=lambda u:abs(u['y']-h['y']))
        for year,x,header_word in columns:
            cells=[w for w in row['words'] if w[0]>=left and parse_number(w[4]) is not None and abs((w[0]+w[2])/2-x)<distance]
            if len(cells)!=1:continue
            w=cells[0]
            found.append({'metric':metric,'row_label':' '.join(t[4] for t in label_words),'year':year,'value':str(parse_number(w[4])),
                          'source_scale':unit,'value_bbox':list(w[:4]),'row_bbox':bbox(row['words']),
                          'year_header_bbox':list(header_word[:4]),'period_header_text':h['text'],'period_header_bbox':bbox(h['words']),
                          'scale_header_text':unit_row['text'],'scale_header_bbox':bbox(unit_row['words']),'column_mode':mode,'value_text':w[4]})
    return found

def to_millions(value,unit):
    if type(value) is bool:raise ValueError('Boolean amount')
    v=Decimal(str(value));key=re.sub('[^a-z$]','',str(unit).lower())
    factors={}
    for name,factor in [('thousand',Decimal('.001')),('million',Decimal(1)),('billion',Decimal(1000))]:
        for alias in [name,name+'s','usd'+name,'usd'+name+'s',name+'usd',name+'susd',name+'ofusd',name+'sofusd',name+'ofusdollars',name+'sofusdollars']:factors[alias]=factor
    factors.update({'usd':Decimal('.000001'),'dollars':Decimal('.000001'),'$':Decimal('.000001')})
    if key not in factors or not v.is_finite():raise ValueError('Unknown currency/scale or nonfinite value')
    return v*factors[key]

def bind_answer(answer,spec,role_metrics,doc_id,supplied_pages,page_cache):
    raw=copy.deepcopy(answer);bindings=[];problems=[]
    if not isinstance(answer,dict) or type(answer.get('abstain')) is not bool:return {'status':'held_for_review','reasons':['invalid_answer'],'bindings':[],'source_verified':False}
    if answer['abstain']:return {'status':'abstained','reasons':[],'bindings':[],'source_verified':False}
    if spec is None or role_metrics is None:return {'status':'held_for_review','reasons':['unsupported_task_or_formula'],'bindings':[],'source_verified':False}
    for role in spec['roles']:
        candidates=[]
        for i,v in enumerate(answer.get('source_values',[])):
            if not isinstance(v,dict):continue
            try:year=normalize_year(v.get('year'))
            except ValueError:continue
            if year==role['year'] and re.search(role['label_pattern'],str(v.get('label','')),re.I):candidates.append((i,v))
        result={'role':role['name'],'metric':role_metrics[role['name']],'expected_year':role['year']}
        if len(candidates)!=1:result.update(status='held',reason='ambiguous_or_missing_operand')
        else:
            i,v=candidates[0];result['source_field_index']=i;page=v.get('pdf_page_index')
            result['cited_page']=page
            if type(page) is not int or page not in supplied_pages or (doc_id,page) not in page_cache:result.update(status='held',reason='unsupplied_page')
            else:
                p=page_cache[doc_id,page];cells=extract_cells(p,result['metric']);cells=[c for c in cells if c['year']==role['year']]
                if len(cells)!=1:result.update(status='held',reason='unique_row_year_cell_not_resolved',candidate_cells=len(cells))
                else:
                    cell=cells[0];result.update(cell=cell,asset_id=p['asset_id'],document_sha256=p['document_sha256'])
                    try:
                        if type(v.get('value')) not in (int,float):raise ValueError('JSON numeric amount required')
                        model=to_millions(v['value'],v.get('unit'));source=to_millions(cell['value'],cell['source_scale'])
                        result.update(model_amount_millions=str(model),source_amount_millions=str(source))
                        result.update(status='matched' if model==source else 'held',reason=None if model==source else 'row_year_value_mismatch')
                    except (ValueError,InvalidOperation):result.update(status='held',reason='unrecognized_model_unit_or_amount')
        if result['status']!='matched':problems.append(role['name']+':'+result['reason'])
        bindings.append(result)
    return {'status':'table_cell_match' if not problems else 'held_for_review','bindings':bindings,'reasons':problems,
            'source_verified':False,'raw_evidence_unchanged':answer==raw,
            'limits':'Scoped machine match of supported rows/periods/scales against PDF text geometry. USD/report currency is a task assumption; independent source audit and broader parser validation remain pending.'}
