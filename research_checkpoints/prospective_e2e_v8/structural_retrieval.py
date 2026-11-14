"""Statement-title seeds plus BM25; fixed question/document rules, no gold input."""
import re
from retrieval import rank

PATTERNS={
    'balance':re.compile(r'^(?:condensed\s+)?consolidated\s+balance\s+shee\s*ts?$',re.I),
    'income':re.compile(r'^(?:condensed\s+)?consolidated\s+statements?\s+of\s+(?:income|operations|earnings)$',re.I),
}

def kinds(question):
    q=question.lower()
    if any(t in q for t in ['turnover','pp&e between']):return ['balance','income']
    if any(t in q for t in ['working capital','current liabilities','current assets','net ppne','balance sheet','financial position']):return ['balance']
    return ['income']

def page_kinds(text):
    lines=[re.sub(r'\s+',' ',line).strip() for line in text.splitlines() if line.strip()][:12]
    return [kind for kind,pattern in PATTERNS.items() if any(pattern.fullmatch(line) for line in lines)]

def structural_rank(question,pages):
    bm=rank(question,pages);lookup={p['pdf_page_index']:p for p in pages}
    wanted=kinds(question)
    eligible={kind:[r for r in bm if kind in page_kinds(lookup[r['pdf_page_index']]['text'])] for kind in wanted}
    seeds=[]
    for kind in wanted:
        if eligible[kind]:
            row=dict(eligible[kind][0]);row['selection_reason']='statement_title_seed:'+kind;seeds.append(row)
    seen={r['pdf_page_index'] for r in seeds}
    remainder=[]
    for row in bm:
        if row['pdf_page_index'] in seen:continue
        row=dict(row);row['selection_reason']='bm25_fill';remainder.append(row)
    return seeds+remainder
