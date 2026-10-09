"""Fixed question-only development rules; these are search cues, not formulas."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from finocr.retrieval.bm25 import RetrievalQuery, tokenize
from finocr.retrieval.stopwords import tokenize_without_stopwords


EXPANSION_VERSION = "financial-question-terms-v1"


@dataclass(frozen=True, slots=True)
class ExpansionRule:
    rule_id: str
    phrases: tuple[str, ...]
    terms: str


# Generic statement/operand vocabulary. No report, company, page, value, or
# benchmark-specific answer is stored. No transitive expansion or formula solving.
RULES = (
    ExpansionRule("quick_ratio", ("quick ratio", "quick ratios", "acid test ratio"),
                  "cash equivalents short term investments marketable securities accounts receivable current liabilities"),
    ExpansionRule("current_ratio", ("current ratio", "current ratios"),
                  "current assets liabilities"),
    ExpansionRule("gross_margin", ("gross margin", "gross margins", "gross profit margin", "gross profit margins"),
                  "gross profit revenue revenues net sales cost goods sold"),
    ExpansionRule("operating_margin", ("operating margin", "operating margins", "operating profit margin"),
                  "operating income profit revenue revenues net sales"),
    ExpansionRule("net_margin", ("net margin", "net margins", "net profit margin", "net income margin"),
                  "net income earnings revenue revenues sales"),
    ExpansionRule("ebitda", ("ebitda",),
                  "operating income profit depreciation amortization"),
    ExpansionRule("ebit", ("ebit",), "operating income profit"),
    ExpansionRule("capital_expenditure", ("capex", "capital expenditure", "capital expenditures", "capital spending"),
                  "capital expenditures spending purchases property plant equipment"),
    ExpansionRule("depreciation_amortization", ("d a", "depreciation and amortization", "depreciation amortization"),
                  "depreciation amortization cash flows"),
    ExpansionRule("return_on_assets", ("return on assets", "roa"), "net income total assets"),
    ExpansionRule("return_on_equity", ("return on equity", "roe"),
                  "net income shareholders stockholders equity"),
    ExpansionRule("debt_to_equity", ("debt to equity", "debt equity"),
                  "debt borrowings shareholders stockholders equity"),
)


def policy_record() -> dict:
    rules = [{"rule_id": r.rule_id, "phrases": list(r.phrases),
              "terms": tokenize_without_stopwords(r.terms)} for r in RULES]
    policy = {"version": EXPANSION_VERSION, "rules": rules,
            "match_policy": "contiguous original question tokens; all matching rules; no recursive expansion",
            "term_policy": "append sorted distinct absent content tokens; binary BM25 query frequency",
            "maximum_added_terms": 32, "truncation_policy": "alphabetical first 32"}
    policy["sha256"] = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return policy


def expand_query(query: RetrievalQuery) -> tuple[RetrievalQuery, dict]:
    if not isinstance(query, RetrievalQuery):
        raise TypeError("Expansion accepts only the minimal RetrievalQuery schema")
    original_tokens = tokenize(query.question)
    existing = set(tokenize_without_stopwords(query.question))
    matched, additions = [], set()
    for rule in RULES:
        for phrase in rule.phrases:
            tokens = tokenize(phrase)
            if any(original_tokens[i:i + len(tokens)] == tokens
                   for i in range(len(original_tokens) - len(tokens) + 1)):
                matched.append(rule.rule_id)
                additions.update(tokenize_without_stopwords(rule.terms))
                break
    candidates = sorted(additions - existing)
    added = candidates[:32]
    # Keep original wording, signs, years, and negation; append content tokens only.
    question = query.question + (" " + " ".join(added) if added else "")
    return RetrievalQuery(query.task_id, query.doc_id, question), {
        "task_id": query.task_id, "doc_id": query.doc_id, "matched_rule_ids": matched,
        "added_terms": added, "discarded_term_count": len(candidates) - len(added),
        "original_content_token_count": len(tokenize_without_stopwords(query.question)),
        "expanded_content_token_count": len(tokenize_without_stopwords(question)),
    }
