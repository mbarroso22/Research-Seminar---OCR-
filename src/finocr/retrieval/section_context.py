"""Deterministic, query-independent weak headings from raw native-text lines."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, normalize_search_text
from finocr.retrieval.stopwords import tokenize_without_stopwords


SECTION_VERSION = "source-local-headings-v1"
MAX_HEADING_TOKENS = 64
HEADING_WEIGHT = 0.25
_ITEM = r"(?i)^Item\s+\d{1,2}[A-C]?\.?\s+\S.+$"
_STATEMENT = r"(?i)^(?:Consolidated (?:Statements? of .+|Balance Sheets?)|Notes to Consolidated Financial Statements)(?:\s*\(continued\))?$"
_NOTE = r"(?i)^Note\s+\d{1,2}\s*[:.\u2014\-]\s*\S.+$"
_RISK = r"(?i)^Risks Related to\s+\S.+$"
_RISK_SENTENCE = r"^(?:We (?:depend|conduct|derive)\b|Changes in levels of\b)"
_EXHIBIT = r"(?i)^Exhibit\s+\d+(?:\.\d+)?[A-Z]?$"
_REFERENCE = r"(?i)^(?:(?:Item|Article|Section|Note)\s+[\dIVX]+[A-C]?\.?\s+)?[^\d$%]{3,140}\s+\d{1,3}(?:[\u2013\-]\d{1,3})?$"
_RESET = {"signatures", "index to exhibits", "exhibit index"}
_NAVIGATION = {"table of contents", "contents"}
_RULES = [("item", _ITEM), ("statement", _STATEMENT), ("note", _NOTE), ("risk_group", _RISK)]
_TITLE_LOWER = frozenset("a an and at by for from in of on or the to with".split())


def section_policy_record() -> dict:
    policy = {
        "version": SECTION_VERSION, "heading_weight": HEADING_WEIGHT,
        "maximum_page_heading_tokens": MAX_HEADING_TOKENS,
        "token_budget": "frozen stopword tokenizer; complete headings only; source/scope order; skip overflow",
        "rules": [{"kind": kind, "pattern": pattern} for kind, pattern in _RULES],
        "risk_sentence_prefix": _RISK_SENTENCE, "exhibit_pattern": _EXHIBIT,
        "contents_reference_pattern": _REFERENCE, "contents_minimum_reference_lines": 6,
        "reset_lines": sorted(_RESET), "navigation_lines": sorted(_NAVIGATION),
        "title_rule": "2..12 words; <=120 characters; letters/hyphens/apostrophes/& only; title case or all caps; no terminal punctuation",
        "title_lowercase_words": sorted(_TITLE_LOWER),
        "candidate_limits": "<=32 stopword tokens and <=240 normalized characters; risk sentences <=2 consecutive raw lines, second starts lowercase, ending period",
        "continuation": "last observed local heading to next physical page only; opening span ends at first heading/reset; no chaining or future pages",
        "resets": "new report; blank/navigation/footer-only text; contents listing; signatures/index-to-exhibits; standalone top-three-line exhibit; filing cover",
        "scope": "raw Unicode offsets [start,end); local spans end at next heading/reset; inherited spans are weak inference",
        "duplicates": "normalized casefold heading text once per page; observed/inherited entries retained with rejection reasons",
        "ranking": "unchanged expansion BM25 body score + 0.25 * separate heading BM25 score; all physical pages; (-score,page_index)",
        "variables": "no year/currency/unit propagation; no adjacency, question cleanup, ledger or model calls",
    }
    policy["sha256"] = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return policy


@dataclass(frozen=True, slots=True)
class SourcePage:
    doc_id: str
    page_index: int
    raw_text: str

    def __post_init__(self):
        if (not isinstance(self.doc_id, str) or not self.doc_id or type(self.page_index) is not int
                or self.page_index < 0 or not isinstance(self.raw_text, str)):
            raise ValueError("Source pages require doc_id, nonnegative integer page_index and raw_text")

    @classmethod
    def from_record(cls, record: dict) -> "SourcePage":
        doc, page, raw = (record.get(key) for key in ("doc_id", "page_index", "raw_text"))
        return cls(doc, page, raw)


def _lines(raw):
    offset = 0
    result = []
    for line in raw.splitlines(keepends=True):
        text = line.strip()
        if text:
            start = offset + len(line) - len(line.lstrip())
            result.append({"text": text, "start": start, "end": start + len(text)})
        offset += len(line)
    return result


def _title(text):
    words = text.split()
    if not 2 <= len(words) <= 12 or len(text) > 120 or not re.fullmatch(r"[A-Za-z\u00c0-\u024f\u2019'&\- ]+", text):
        return False
    parts = [p for word in words for p in word.split("-") if p and p != "&"]
    return bool(parts) and all(part[0].isupper() or (i > 0 and part in _TITLE_LOWER) for i, part in enumerate(parts))


def _observe(page):
    lines = _lines(page.raw_text)
    meaningful = [line for line in lines if line["text"].casefold() not in _NAVIGATION and not line["text"].isdigit()]
    resets, headings = [], []
    contents = sum(bool(re.fullmatch(_REFERENCE, line["text"])) for line in meaningful) >= 6
    # A dense page-reference list is a contents page even if it lacks a contents title.
    if contents:
        resets.append({"offset": 0, "reason": "contents_listing"})
        return headings, resets, meaningful
    consumed = set()
    for i, line in enumerate(meaningful):
        if i in consumed:
            continue
        text, key = line["text"], line["text"].casefold()
        reason = None
        if key in _RESET:
            reason = key.replace(" ", "_")
        elif i < 3 and re.fullmatch(_EXHIBIT, text):
            reason = "exhibit_start"
        elif i < 3 and key == "united states" and any("SECURITIES AND EXCHANGE COMMISSION" in r["text"] for r in meaningful[i + 1:i + 3]):
            reason = "filing_cover"
        if reason:
            resets.append({"offset": line["start"], "reason": reason})
            continue
        if key in {"part i", "part ii", "part iii", "part iv"} or re.fullmatch(_REFERENCE, text):
            continue
        kind = next((kind for kind, pattern in _RULES if re.fullmatch(pattern, text)), None)
        end = line["end"]
        if kind is None and re.match(_RISK_SENTENCE, text):
            kind = "risk_sentence"
            if not text.endswith(".") and i + 1 < len(meaningful):
                following = meaningful[i + 1]
                gap = page.raw_text[line["end"]:following["start"]]
                if following["text"][0].islower() and gap.isspace() and gap.count("\n") <= 1:
                    text += " " + following["text"]
                    end = following["end"]
                    consumed.add(i + 1)
            if not text.endswith("."):
                kind = None
        if kind is None and _title(text):
            kind = "title"
        if kind and len(normalize_search_text(text)) <= 240 and len(tokenize_without_stopwords(text)) <= 32:
            start = line["start"]
            headings.append({"kind": kind, "heading_text": page.raw_text[start:end],
                             "source_page_index": page.page_index, "source_start": start, "source_end": end})
    return headings, resets, meaningful


def build_section_context(pages: list[SourcePage]) -> list[dict]:
    """Only SourcePage objects accepted. Every report page is emitted, including blanks."""
    return _build_context(pages, _observe)


def _build_context(pages, observe):
    """Shared scope/continuation/budget assembly; observers cannot change these rules."""
    if not pages or any(not isinstance(page, SourcePage) for page in pages):
        raise TypeError("Section construction accepts only a nonempty list of minimal SourcePage objects")
    doc_id = pages[0].doc_id
    if any(page.doc_id != doc_id or page.page_index != i for i, page in enumerate(pages)):
        raise ValueError("Context construction requires one report in contiguous zero-based physical order")
    output, active = [], None
    for page in pages:
        observed, resets, meaningful = observe(page)
        blank = not meaningful
        if blank:
            resets.append({"offset": 0, "reason": "blank_or_navigation_only"})
        boundaries = sorted([h["source_start"] for h in observed] + [r["offset"] for r in resets])
        entries = []
        opening = meaningful[0]["start"] if meaningful else 0
        if active is not None and active["source_page_index"] == page.page_index - 1 and not blank:
            end = boundaries[0] if boundaries else len(page.raw_text)
            if end > opening:
                entries.append({**active, "mode": "inherited", "scope_start": opening, "scope_end": end})
        for heading in observed:
            start = heading["source_start"]
            end = next((offset for offset in boundaries if offset > start), len(page.raw_text))
            entries.append({**heading, "mode": "observed", "scope_start": start, "scope_end": end})
        tokens, seen = [], set()
        for entry in entries:
            key = normalize_search_text(entry["heading_text"]).casefold()
            added = tokenize_without_stopwords(entry["heading_text"])
            reason = ("duplicate_heading" if key in seen else "heading_token_cap" if len(tokens) + len(added) > MAX_HEADING_TOKENS else None)
            seen.add(key)
            entry["included"] = reason is None
            entry["rejection_reason"] = reason
            if reason is None:
                tokens.extend(added)
        output.append({"doc_id": doc_id, "page_index": page.page_index, "page_index_base": 0,
                       "headings": entries, "resets": resets, "heading_tokens": tokens,
                       "heading_token_count": len(tokens)})
        # Carry only a locally observed heading after the final reset, never inherited state.
        last_reset = max((r["offset"] for r in resets), default=-1)
        eligible = [h for h in observed if h["source_start"] > last_reset]
        active = eligible[-1] if eligible and not blank else None
    return output


def rank_with_section_context(body: BM25Index, headings: BM25Index, query: RetrievalQuery) -> list[dict]:
    if body.doc_id != headings.doc_id or set(body.counts) != set(headings.counts):
        raise ValueError("Body and heading indexes must have the same report and full page candidates")
    original = {r["page_index"]: r["score"] for r in body.rank(query)}
    context = {r["page_index"]: r["score"] for r in headings.rank(query)}
    return sorted([{"page_index": page, "body_score": score, "heading_score": context[page],
                    "weighted_heading_score": HEADING_WEIGHT * context[page],
                    "score": score + HEADING_WEIGHT * context[page]} for page, score in original.items()],
                  key=lambda r: (-r["score"], r["page_index"]))
