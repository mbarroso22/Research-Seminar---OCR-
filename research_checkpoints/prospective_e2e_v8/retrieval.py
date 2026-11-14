"""Fixed native-text BM25 within the supplied document identity; no references."""
import collections
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STOP=set('a an and are as at be been between by can company details did do does end for from give has have how if in information is it its like many much of on only or our out please primarily provided question relying round shown state statement statements than that the their then these this to units use using was we what when which who with year years you your'.split())
ALIASES={
    'ppne':'property plant equipment net',
    'cogs':'cost goods sold sales products',
    'working capital':'current assets current liabilities',
    'inventory turnover':'inventories cost goods sold',
    'operating income':'operating income revenues revenue',
}

def tokens(text,expand=False):
    text=text.lower().replace('pp&e','ppne')
    text=re.sub(r'\bfy(?=\d{4}\b)','',text)
    if expand:
        extra=' '.join(value for key,value in ALIASES.items() if key in text)
        text+=' '+extra
    return [t for t in re.findall(r'[a-z0-9]+',text) if t not in STOP]

def rank(question,pages,k1=1.2,b=.75):
    docs=[collections.Counter(tokens(p['text'])) for p in pages]
    lengths=[sum(d.values()) for d in docs]
    average=sum(lengths)/len(lengths) or 1
    query=set(tokens(question,True))
    df={term:sum(term in d for d in docs) for term in query}
    rows=[]
    for p,d,length in zip(pages,docs,lengths):
        score=0.0
        for term in sorted(query):
            tf=d[term]
            if not tf:continue
            idf=math.log(1+(len(docs)-df[term]+.5)/(df[term]+.5))
            score+=idf*tf*(k1+1)/(tf+k1*(1-b+b*length/average))
        rows.append({'pdf_page_index':p['pdf_page_index'],'score':score})
    return sorted(rows,key=lambda x:(-x['score'],x['pdf_page_index']))

def verify():
    queries=json.loads((ROOT/'prepared/queries.json').read_text(encoding='utf-8'))
    pages=json.loads((ROOT/'provenance/native_pages.json').read_text(encoding='utf-8'))
    expected=json.loads((ROOT/'provenance/bm25_rankings.json').read_text(encoding='utf-8'))
    for q in queries:
        actual=rank(q['question'],[p for p in pages if p['doc_id']==q['doc_id']])
        old=expected[q['case_id']]['ranking']
        assert len(actual)==len(old)
        assert all(a['pdf_page_index']==b['pdf_page_index'] and abs(a['score']-b['score'])<1e-9 for a,b in zip(actual,old))
    print('Retrieval replay: passed for 6 actual questions; no model calls')

if __name__=='__main__':
    verify()
