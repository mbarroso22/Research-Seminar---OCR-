"""Six hard-coded fictional cases. There is no benchmark input-file option."""
from __future__ import annotations
from copy import deepcopy
from .contract import messages, MAX_INPUT


def historical_cases_v2() -> list[dict]:
    specifications = [
        ("signed", "What was fictional Cedar Works' FY2031 operating cash flow in USD millions?", "Cedar Works FY2031. Operating cash flow: (12.5) USD million."),
        ("scale", "Express fictional Cedar Works' FY2031 revenue in USD millions.", "Cedar Works FY2031 revenue was 1.25 USD billion."),
        ("margin", "Calculate fictional Cedar Works' FY2031 gross margin and its percentage-point change from FY2030.", "Cedar Works FY2031: revenue 240 USD million; cost of sales 180 USD million. FY2030 gross margin was 20 percent."),
        ("comparison", "Which activity supplied most cash in FY2031, and did profit improve?", "Cedar Works FY2031 cash flows in USD million: operations 40; investing (12); financing (9). Revenue rose, but profit declined because input costs increased."),
        ("missing", "Calculate fictional Cedar Works' FY2031 quick ratio.", "Cedar Works FY2031: cash 10 USD million; accounts receivable 5 USD million. Current liabilities were not supplied."),
        ("capacity", "Can fictional Cedar Works' FY2031 quick ratio be calculated from this packet?", "Fictional Cedar Works FY2031. Current liabilities were not supplied. " + "Capacity filler. " * 1800),
    ]
    return [{"task_id": "synthetic:" + name, "doc_id": "synthetic:cedar-works-fy2031",
             "question": question, "pages": [{"page_id": page, "raw_text": text if page == 0 or name == 'capacity' else ""} for page in range(5)]}
            for name, question, text in specifications]


CASE_VERSION = 'fictional-cases-v3-offline'


def cases() -> list[dict]:
    result = historical_cases_v2()
    result[-1]['question'] = "Calculate fictional Cedar Works' FY2031 quick ratio from this packet."
    return result


def pad_to(text: str, target: int, count) -> str:
    """Exact local tokenizer count, bounded attempts; no inference calls."""
    result = text
    for _ in range(32):
        gap = target - count(result)
        if gap == 0: return result
        if gap < 0: raise ValueError('Padding overshot the exact capacity; preserve setup failure')
        result += " x" * gap
    raise ValueError('Could not construct exact token boundary')


def _pack(case: dict, tokenizer, make_messages) -> tuple[list[dict], dict]:
    case = deepcopy(case)
    retained = []
    for p in case['pages']:
        raw = p['raw_text']
        tokens = tokenizer.encode(raw, add_special_tokens=False)
        selected = tokens[:800]
        prefix = tokenizer.decode(selected, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        while selected and (not raw.startswith(prefix) or '\ufffd' in prefix or len(tokenizer.encode(prefix, add_special_tokens=False)) > 800):
            selected.pop()
            prefix = tokenizer.decode(selected, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        if not raw.startswith(prefix): raise ValueError('Tokenizer cannot preserve source prefix')
        p['raw_text'] = prefix + ('\n[truncated]' if len(tokens) > len(selected) else '')
        retained.append({'page_id': p['page_id'], 'source_tokens': len(tokens), 'retained_interval': [0, len(selected)],
                         'retained_token_ids': selected, 'truncated': len(tokens) > len(selected)})
    count = lambda text: len(tokenizer.encode(text, add_special_tokens=False))
    if case['task_id'] == 'synthetic:capacity':
        # A long fictional report ID fills packet overhead to 4096, while each
        # page body stays <=800. System padding fills the independent 1024 cap.
        def packet_count(doc_id):
            m = make_messages({**case, 'doc_id': doc_id})
            return count(m[1]['content'].split('\n\n', 1)[1])
        case['doc_id'] = pad_to(case['doc_id'], 4096, packet_count)
    turns = make_messages(case)
    render = lambda turns: tokenizer.apply_chat_template(turns, tokenize=False, add_generation_prompt=True)
    if case['task_id'] == 'synthetic:capacity':
        turns[0]['content'] = pad_to(turns[0]['content'], MAX_INPUT,
            lambda system: count(render([{'role': 'system', 'content': system}, turns[1]])))
    prompt = render(turns)
    packet = turns[1]['content'].split('\n\n', 1)[1]
    evidence_count, total = count(packet), count(prompt)
    if evidence_count > 4096 or total - evidence_count > 1024 or total > MAX_INPUT:
        raise ValueError('Input/evidence/overhead budget violation')
    return turns, {'retained': retained, 'evidence_tokens': evidence_count,
                   'overhead_tokens': total-evidence_count, 'input_tokens': total, 'prompt': prompt,
                   'token_ids': tokenizer.encode(prompt, add_special_tokens=False),
                   'capacity_padding_only': case['task_id'] == 'synthetic:capacity'}


def pack(case: dict, tokenizer) -> tuple[list[dict], dict]:
    return _pack(case, tokenizer, messages)


def pack_historical_v2(case: dict, tokenizer) -> tuple[list[dict], dict]:
    from .historical_contract_v2 import messages as historical_messages
    return _pack(case, tokenizer, historical_messages)
