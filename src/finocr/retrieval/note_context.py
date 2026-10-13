"""Final heading-format ablation; source-only, causal numbered-note eligibility."""
from __future__ import annotations

import hashlib
import json
import re

from finocr.retrieval import section_context as v1
from finocr.retrieval.bm25 import normalize_search_text
from finocr.retrieval.stopwords import tokenize_without_stopwords


NOTE_VERSION = "source-local-headings-note-formats-v1"
_EN_DASH_NOTE = r"(?i)^Note\s+\d{1,2}\s*\u2013\s*\S.+$"
_PARENT = r"(?i)^Notes to Consolidated Financial Statements(?:\s*\(continued\))?$"
_BARE = r"^([1-9]\d?)\.\s+(.+)$"


def note_policy_record():
    policy = {
        "version": NOTE_VERSION, "section_v1_policy": v1.section_policy_record(),
        "en_dash_note_pattern": _EN_DASH_NOTE, "notes_parent_pattern": _PARENT,
        "bare_note_pattern": _BARE,
        "bare_title": "1..12 words; <=120 characters; v1 title-case/letter/hyphen/apostrophe/& grammar; no numbers, terminal punctuation or page references",
        "eligibility": "exact standalone parent; first bare note must be 1 on the parent page; thereafter strictly next integer; no gaps/repeats/backward acceptance; repeated parent preserves chain",
        "eligibility_resets": "new report; every v1 reset; blank/navigation/footer-only page; observed Item boundary; no eligibility from prose mentions or future pages",
        "region_state": "recognition only; parent page and last bare-note number; no heading text, year, unit or value propagation",
        "audit": "all bare-pattern candidates, accepted/rejected reasons, parent/reset events and before/after region state; raw source character spans",
        "unchanged": "v1 scopes, one-page continuation, duplicate policy, 64-token cap, 0.25 weight, BM25, stopwords, tokenization, expansion v1, full candidates and zero-based IDs",
        "known_limits": "title-shaped sequential lists inside an eligible notes region remain ambiguous; missing/wrapped/unsupported note 1 prevents chain start; gaps keep later numbers rejected while the expected next integer is missing; no generic/prose heading cleanup",
    }
    policy["sha256"] = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return policy


def _bare_title(title):
    # Adding a generic first word reuses the frozen title grammar for one-word titles.
    words = title.split()
    if not 1 <= len(words) <= 12 or len(title) > 120 or not words[0][0].isupper():
        return False
    return v1._title("Note " + title) if len(words) == 1 else v1._title(title)


def build_note_context(pages: list[v1.SourcePage]) -> list[dict]:
    """Accept only minimal source pages; do not load queries or annotation metadata."""
    state = {"parent_page_index": None, "last_bare_number": None}
    audits = []

    def observe(page):
        before = dict(state)
        headings, resets, meaningful = v1._observe(page)
        events, candidates = [], []
        reset_at = {r["offset"]: r["reason"] for r in resets}
        item_starts = {h["source_start"] for h in headings if h["kind"] == "item"}
        contents = any(r["reason"] == "contents_listing" for r in resets)

        def clear(offset, reason):
            state.update(parent_page_index=None, last_bare_number=None)
            events.append({"offset": offset, "event": "eligibility_reset", "reason": reason})

        if contents or not meaningful:
            clear(0, "contents_listing" if contents else "blank_or_navigation_only")
        for line in v1._lines(page.raw_text):
            text, start, end = line["text"], line["start"], line["end"]
            if not contents and start in reset_at:
                clear(start, reset_at[start])
            if start in item_starts:
                clear(start, "item_boundary")
            if not contents and re.fullmatch(_PARENT, text):
                if state["parent_page_index"] is None:
                    state["parent_page_index"] = page.page_index
                events.append({"offset": start, "event": "notes_parent", "source_end": end})
            if not contents and not re.fullmatch(v1._REFERENCE, text) and re.fullmatch(_EN_DASH_NOTE, text):
                if len(normalize_search_text(text)) <= 240 and len(tokenize_without_stopwords(text)) <= 32:
                    headings.append({"kind": "note_en_dash", "heading_text": page.raw_text[start:end],
                                     "source_page_index": page.page_index, "source_start": start, "source_end": end})
            match = re.fullmatch(_BARE, text)
            if not match:
                continue
            number, title = int(match[1]), match[2]
            reason = ("contents_listing" if contents else
                      "outside_notes_region" if state["parent_page_index"] is None else
                      "unsupported_title_syntax" if not _bare_title(title) or re.fullmatch(v1._REFERENCE, text) else
                      "candidate_limits" if len(normalize_search_text(text)) > 240
                      or len(tokenize_without_stopwords(text)) > 32 else
                      "first_note_requires_local_parent_and_one" if state["last_bare_number"] is None
                      and (number != 1 or state["parent_page_index"] != page.page_index) else
                      "nonsequential_note_number" if state["last_bare_number"] is not None
                      and number != state["last_bare_number"] + 1 else None)
            candidates.append({"source_page_index": page.page_index, "source_start": start, "source_end": end,
                               "heading_text": page.raw_text[start:end], "number": number,
                               "accepted": reason is None, "rejection_reason": reason})
            if reason is None:
                state["last_bare_number"] = number
                headings.append({"kind": "note_bare_number", "heading_text": page.raw_text[start:end],
                                 "source_page_index": page.page_index, "source_start": start, "source_end": end})
        audits.append({"state_before": before, "events": events, "candidates": candidates, "state_after": dict(state)})
        return sorted(headings, key=lambda h: h["source_start"]), resets, meaningful

    contexts = v1._build_context(pages, observe)
    for row, audit in zip(contexts, audits):
        row["note_detection"] = audit
    return contexts
