"""Conservative offline binding v3; no reference values, network or citation repair.

Currency provenance and task semantics are locked caller policy, not model output.
Unknown supplemental fields stay held. All source normalization is traceable.
"""
import copy
from decimal import Decimal, InvalidOperation, localcontext
import re

from legacy import binding_v2 as old, normalize_year

VERSION=3
SUPPLEMENTAL_POLICY='hold_all_unbound_fields_v1'
SCALE_FACTORS={'dollars':Decimal('.000001'),'thousands':Decimal('.001'),
               'millions':Decimal(1),'billions':Decimal(1000)}
NOTE_SUFFIX=re.compile(r'\s*\(notes?\s+\d+(?:(?:\s*,\s*|\s+and\s+)\d+)*\)\s*$',re.I)
CURRENCY=r'(?:usd|u\.?s\.? dollars?|united states dollars?|dollars?|\$)'
SCALE=r'(?:thousands?|millions?|billions?)'
UNIT_FORMS=[rf'(?P<currency>{CURRENCY})\s+(?:in\s+)?(?P<scale>{SCALE})',
            rf'(?P<currency>{CURRENCY})\s*\(\s*in\s+(?P<scale>{SCALE})\s*\)',
            rf'(?:in\s+)?(?P<scale>{SCALE})(?:\s+(?:of\s+)?(?P<currency>{CURRENCY}))?',
            rf'(?P<currency>{CURRENCY})']
TITLE_PATTERNS={
 'balance':r'^(?:[a-z0-9 ]+ )?consolidated (?:balance sheets?|statements? of financial position)$',
 'income':r'^(?:[a-z0-9 ]+ )?consolidated statements? of (?:income|operations|earnings)$'}
BALANCE_METRICS={'ppne','inventory','current_assets','current_liabilities'}


def checked_context(context,doc_id,page):
    if not isinstance(context,dict) or context.get('doc_id')!=doc_id:
        raise ValueError('missing_or_wrong_document_context')
    if context.get('document_sha256')!=page.get('document_sha256'):
        raise ValueError('document_fingerprint_mismatch')
    if context.get('reporting_currency')!='USD':
        raise ValueError('unsupported_or_unknown_reporting_currency')
    if not isinstance(context.get('currency_basis'),dict) or not context['currency_basis'].get('evidence_text'):
        raise ValueError('missing_reporting_currency_provenance')
    if context['currency_basis'].get('document_sha256')!=context['document_sha256']:
        raise ValueError('currency_provenance_fingerprint_mismatch')
    return context


def normalize_unit(unit,context):
    if not isinstance(context,dict) or context.get('reporting_currency')!='USD' or not context.get('currency_basis'):
        raise ValueError('reporting_currency_required')
    if not isinstance(unit,str) or not unit.strip():
        raise ValueError('missing_unit')
    text=' '.join(unit.casefold().split())
    match=None
    for form in UNIT_FORMS:
        match=re.fullmatch(form,text)
        if match:break
    if match is None:
        raise ValueError('unknown_ambiguous_or_contradictory_unit')
    groups=match.groupdict();scale=groups.get('scale') or 'dollars'
    if not scale.endswith('s'):scale+='s'
    currency=groups.get('currency')
    factor=SCALE_FACTORS[scale]
    return {'original_unit':unit,'reporting_currency':'USD','source_scale':scale,
            'factor_to_usd_millions':str(factor),'canonical_unit':'USD millions',
            'currency_resolution':'explicit_USD' if currency and currency not in ['dollar','dollars','$'] else 'locked_document_currency',
            'currency_basis':copy.deepcopy(context['currency_basis'])}


def strip_note_suffix(label):
    stripped=NOTE_SUFFIX.sub('',label)
    return stripped,[] if stripped==label else [{'kind':'recognized_note_suffix','original':label,'matching_text':stripped}]


def label_matches(label,metric,role_context,model_year=None):
    if metric not in old.METRICS or not isinstance(label,str):return False,[]
    normalized,trace=strip_note_suffix(label)
    if model_year is not None:
        trimmed=re.sub(r'[,\s]+(?:(?:FY|fiscal)\s*)?'+str(model_year)+r'\s*$','',normalized,flags=re.I)
        if trimmed!=normalized:trace.append({'kind':'model_year_suffix','original':normalized,'matching_text':trimmed})
        normalized=trimmed
    key=old.norm(normalized)
    patterns=list(old.METRICS[metric])
    if model_year is not None:
        patterns+= {'ppne':[r'^(?:net )?ppne$',r'^pp and e$',r'^net property plant and equipment$'],
                    'inventory':[r'^total inventories$'],
                    'current_assets':[r'^current assets$'],
                    'current_liabilities':[r'^current liabilities$'],
                    'cogs':[r'^cogs$']}.get(metric,[])
    if any(re.fullmatch(p,key) for p in patterns):return True,trace
    if metric=='net_revenues' and role_context.get('revenue_definition')=='consolidated_total_revenues' and re.fullmatch(r'total revenues?',key):
        trace.append({'kind':'context_qualified_total_revenue_alias','original':label,
                      'task_semantics':'consolidated_total_revenues'})
        return True,trace
    return False,trace


def statement_scope(rows,ri,metric):
    kind='balance' if metric in BALANCE_METRICS else 'income'
    titles=[]
    for i,row in enumerate(rows[:ri]):
        text=old.norm(row['text'])
        if set(text.split())&{'not','unconsolidated','nonconsolidated','segment','segments','summary','summaries'}:continue
        # PDF extraction can split a terminal title glyph. Only this literal
        # title-word join is allowed; source row labels/values stay untouched.
        text=re.sub(r'\bbalance shee t\b','balance sheet',text)
        pattern=TITLE_PATTERNS[kind]
        if re.fullmatch(pattern,text):titles.append(i);continue
        # Some issuers share the title line with their corporate name.
        suffix=r'(?: [a-z0-9 ]*(?:incorporated|corporation|company|companies|inc|subsidiaries))'
        if re.fullmatch(pattern[:-1]+suffix+'$',text):titles.append(i)
    if not titles:return False
    # A later table subsection must not inherit a primary statement's scope.
    blockers=[r for r in rows[titles[-1]+1:ri] if re.fullmatch(
        r'(?:segment(?: results| information| data)?|(?:[a-z ]+ )?segment (?:revenues|results)|disaggregated revenues|supplemental (?:data|information))',old.norm(r['text']))]
    return rows[titles[-1]]['text'] if not blockers else False


def extract_cells(page,metric,role_context):
    if page.get('rotation',0)!=0 or metric not in old.METRICS:return []
    rows=old.rows_from_words(page['words']);width=page['width'];found=[]
    for ri,row in enumerate(rows):
        title_text=statement_scope(rows,ri,metric)
        if not title_text:continue
        headers=[]
        for header in rows[:ri]:
            years=[w for w in header['words'] if re.fullmatch(r'(?:19|20)\d{2}',w[4]) and w[0]>width*.5]
            tokens=[t for t in old.norm(header['text']).split() if not t.isdigit()]
            has_scale=bool(re.search(r'\bin\s+(?:thousands|millions|billions)\b',header['text'],re.I))
            allowed=old.HEADER_WORDS|({'dollars','amount','and'} if has_scale else set())
            if len(years)>=2 and len({w[4] for w in years})==len(years) and all(t in allowed for t in tokens):
                headers.append((header,[(int(w[4]),(w[0]+w[2])/2,w) for w in years],'year_columns'))
        mode=None
        if headers:header,columns,mode=headers[-1]
        consolidating=[r for r in rows[:ri] if all(t in r['text'].lower() for t in ['parent','subsidiary','eliminations']) and any(w[4]=='Consolidated' for w in r['words'])]
        if consolidating and (not headers or consolidating[-1]['y']>header['y']):
            ch=consolidating[-1]
            dates=[d for d in rows if d['y']<ch['y'] and ch['y']-d['y']<100 and re.search(r'for the year ended',d['text'],re.I)]
            if not dates:continue
            yy=re.findall(r'\b(?:19|20)\d{2}\b',dates[-1]['text']);cw=[w for w in ch['words'] if w[4]=='Consolidated']
            if len(yy)!=1 or len(cw)!=1:continue
            header=dates[-1];columns=[(int(yy[0]),(cw[0][0]+cw[0][2])/2,cw[0])];mode='consolidated_single_year'
        if mode is None:continue
        if mode=='year_columns':
            gap=min(columns[j+1][1]-columns[j][1] for j in range(len(columns)-1))
            if gap<=0:continue
            left=columns[0][1]-gap*.48;distance=gap*.48
        else:left=width*.40;distance=35
        label_words=[w for w in row['words'] if w[2]<left]
        label=' '.join(w[4] for w in label_words)
        matches,trace=label_matches(label,metric,role_context)
        if not matches:continue
        unit_rows=[r for r in rows if abs(r['y']-header['y'])<80 and r['y']<=row['y'] and re.search(r'\bin\s+(?:thousands|millions|billions)\b',r['text'],re.I)]
        units={u.lower() for r in unit_rows for u in re.findall(r'\bin\s+(thousands|millions|billions)\b',r['text'],re.I)}
        if len(units)!=1:continue
        safe_source_units=True
        for u in unit_rows:
            text=u['text'];scale_match=re.search(r'\bin\s+(thousands|millions|billions)\b',text,re.I)
            prefix=old.norm(text[:scale_match.start()])
            allowed_prefixes={'','amounts','dollars','usd','us dollars','u s dollars','united states dollars','dollars and shares'}
            suffix=text[scale_match.end():].lstrip()
            if prefix not in allowed_prefixes or re.search(r'[€£¥₹₩₽]',text):safe_source_units=False
            if re.match(r'of\b',suffix,re.I) and not re.match(r'of\s+(?:usd|u\.?s\.? dollars?|united states dollars?)\b',suffix,re.I):safe_source_units=False
        if not safe_source_units:continue
        unit=next(iter(units));unit_row=min(unit_rows,key=lambda r:abs(r['y']-header['y']))
        for year,x,header_word in columns:
            values=[w for w in row['words'] if w[0]>=left and old.parse_number(w[4]) is not None and abs((w[0]+w[2])/2-x)<distance]
            if len(values)!=1:continue
            word=values[0]
            found.append({'metric':metric,'row_label':label,'year':year,'value':str(old.parse_number(word[4])),
                          'source_scale':unit,'value_bbox':list(word[:4]),'row_bbox':old.bbox(row['words']),
                          'year_header_bbox':list(header_word[:4]),'period_header_text':header['text'],
                          'period_header_bbox':old.bbox(header['words']),'scale_header_text':unit_row['text'],
                          'scale_header_bbox':old.bbox(unit_row['words']),'column_mode':mode,'value_text':word[4],
                          'recognition_trace':trace,'statement_title_text':title_text,
                          'statement_title_matching_text':re.sub(r'\bbalance shee t\b','balance sheet',old.norm(title_text)),
                          'statement_title_glyph_join_applied':bool(re.search(r'\bbalance shee t\b',old.norm(title_text))),
                          'statement_scope':'primary_consolidated_'+('balance' if metric in BALANCE_METRICS else 'income')})
    return found


def bind_answer(answer,spec,role_metrics,doc_id,supplied_pages,page_cache,document_context,role_contexts=None):
    original=copy.deepcopy(answer);bindings=[];problems=[];used=set();role_contexts=role_contexts or {}
    def finish(status):
        return {'matcher_version':3,'status':status,'bindings':bindings,'reasons':problems,
                'source_verified':False,'raw_evidence_unchanged':answer==original,
                'supplemental_evidence':{'policy':SUPPLEMENTAL_POLICY,
                    'unbound_field_indices':sorted(set(range(len(answer.get('source_values',[]))))-used) if isinstance(answer,dict) and isinstance(answer.get('source_values'),list) else [],
                    'disposition':'preserved; any unbound field prevents calculation'},
                'limits':'Exact cited-page machine cell match under a locked USD reporting-currency and task policy; independent human review and full-answer semantics remain pending.'}
    if not isinstance(answer,dict) or type(answer.get('abstain')) is not bool:
        problems.append('invalid_answer');return finish('held_for_review')
    if answer['abstain']:return finish('abstained')
    if not isinstance(spec,dict) or not isinstance(role_metrics,dict) or not isinstance(answer.get('source_values'),list):
        problems.append('unsupported_task_or_formula');return finish('held_for_review')
    if not isinstance(answer.get('evidence_pages'),list) or any(type(p) is not int or p not in supplied_pages for p in answer['evidence_pages']):
        problems.append('unsupplied_evidence_page');return finish('held_for_review')
    for role in spec['roles']:
        metric=role_metrics.get(role['name']);role_context=role_contexts.get(role['name'],{})
        matches=[]
        for i,field in enumerate(answer['source_values']):
            if not isinstance(field,dict):continue
            try:year=normalize_year(field.get('year'))
            except ValueError:continue
            if year==role['year'] and re.search(role['label_pattern'],str(field.get('label','')),re.I):matches.append((i,field))
        result={'role':role['name'],'metric':metric,'expected_year':role['year']}
        try:
            if len(matches)!=1:raise ValueError('ambiguous_or_missing_operand')
            i,field=matches[0]
            if i in used:raise ValueError('source_field_reused_across_roles')
            used.add(i);page_index=field.get('pdf_page_index')
            result.update(source_field_index=i,cited_page=page_index)
            if type(page_index) is not int or page_index not in supplied_pages or (doc_id,page_index) not in page_cache:
                raise ValueError('unsupplied_page')
            if page_index not in answer['evidence_pages']:raise ValueError('source_page_not_declared')
            page=page_cache[doc_id,page_index]
            if page.get('doc_id')!=doc_id or page.get('pdf_page_index')!=page_index:raise ValueError('page_identity_mismatch')
            context=checked_context(document_context,doc_id,page)
            if field.get('doc_id') is not None and field['doc_id']!=doc_id:raise ValueError('source_document_identity_mismatch')
            if field.get('document_sha256') is not None and field['document_sha256']!=page['document_sha256']:raise ValueError('source_document_fingerprint_mismatch')
            if field.get('asset_id') is not None and field['asset_id']!=page['asset_id']:raise ValueError('asset_identity_mismatch')
            model_label,model_trace=label_matches(field.get('label'),metric,role_context,role['year'])
            if not model_label:raise ValueError('unrecognized_or_qualified_model_metric')
            cells=[c for c in extract_cells(page,metric,role_context) if c['year']==role['year']]
            result['candidate_cells']=len(cells)
            if len(cells)!=1:raise ValueError('unique_row_year_cell_not_resolved')
            cell=cells[0]
            if type(field.get('value')) not in (int,float):raise ValueError('json_numeric_amount_required')
            value=Decimal(str(field['value']))
            if not value.is_finite():raise ValueError('nonfinite_amount')
            normalization=normalize_unit(field.get('unit'),context)
            printed=Decimal(cell['value'])
            with localcontext() as arithmetic:
                arithmetic.prec=max(50,len(value.as_tuple().digits)+8,len(printed.as_tuple().digits)+8)
                model=value*Decimal(normalization['factor_to_usd_millions'])
                source=printed*SCALE_FACTORS[cell['source_scale']]
            result.update(cell=cell,asset_id=page['asset_id'],document_sha256=page['document_sha256'],
                          model_amount_millions=str(model),source_amount_millions=str(source),
                          normalization=normalization,model_label_trace=model_trace)
            if model!=source:raise ValueError('row_year_value_mismatch')
            result.update(status='matched',reason=None)
        except (ValueError,InvalidOperation,KeyError,TypeError) as exc:
            result.update(status='held',reason=str(exc));problems.append(role['name']+':'+str(exc))
        bindings.append(result)
    if used!=set(range(len(answer['source_values']))):problems.append('unbound_source_fields_require_review')
    return finish('held_for_review' if problems else 'table_cell_match')
