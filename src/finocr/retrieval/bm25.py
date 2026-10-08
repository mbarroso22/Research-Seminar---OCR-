from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable


TOKENIZER_VERSION = "unicode-financial-v1"
TOKEN_PATTERN = r"[+\-]?\d+(?:[.,]\d+)*%?|[^\W\d_]+"
_TOKENS = re.compile(TOKEN_PATTERN, re.UNICODE)


def normalize_search_text(text: str) -> str:
    """NFKC, Unicode minus to ASCII minus, whitespace collapse; keep raw separately."""
    return " ".join(unicodedata.normalize("NFKC", text).replace("\u2212", "-").split())


def tokenize(text: str) -> list[str]:
    # No stemming, stopword removal, answer keywords, or query expansion.
    return _TOKENS.findall(normalize_search_text(text).casefold())


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    task_id: str
    doc_id: str
    question: str

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "RetrievalQuery":
        fields = {}
        for name in ("task_id", "doc_id", "question"):
            value = record.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Query {name} must be a nonempty string")
            fields[name] = value
        # Explicit allowlist: never retain task metadata, answers, or labels.
        return cls(**fields)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class BM25Index:
    """One report, all physical pages; empty/failed pages have zero-length text.

    Uses positive log1p IDF and binary query term frequency. All candidates,
    including zero-score ties, are ranked by (-score, zero-based page_index).
    Empty pages count in N and average document length. No labels are accepted.
    """

    def __init__(
        self, doc_id: str, pages: Iterable[tuple[int, str]], *, k1: float = 1.2,
        b: float = 0.75,
    ) -> None:
        if not math.isfinite(k1) or k1 <= 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("BM25 requires finite k1 > 0 and 0 <= b <= 1")
        self.doc_id, self.k1, self.b = doc_id, k1, b
        self.counts: dict[int, Counter[str]] = {}
        for page_index, text in pages:
            if type(page_index) is not int or page_index < 0 or page_index in self.counts:
                raise ValueError("Page indices must be distinct nonnegative integers")
            if not isinstance(text, str):
                raise ValueError("Page text must be a string")
            self.counts[page_index] = Counter(tokenize(text))
        self.lengths = {page: sum(counts.values()) for page, counts in self.counts.items()}
        self.n = len(self.counts)
        self.avgdl = sum(self.lengths.values()) / self.n if self.n else 0.0
        self.df: Counter[str] = Counter()
        for counts in self.counts.values():
            self.df.update(counts.keys())

    def rank(self, query: RetrievalQuery) -> list[dict[str, int | float]]:
        if not isinstance(query, RetrievalQuery):
            raise TypeError("BM25 accepts only the minimal RetrievalQuery schema")
        if query.doc_id != self.doc_id:
            raise ValueError("Query must be scoped to this report")
        terms = sorted(set(tokenize(query.question)))
        scores = []
        for page, counts in self.counts.items():
            score = 0.0
            for term in terms:
                tf = counts[term]
                if not tf:
                    continue
                idf = math.log1p((self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                norm = 1 - self.b + self.b * self.lengths[page] / self.avgdl
                score += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
            scores.append({"page_index": page, "score": score})
        return sorted(scores, key=lambda row: (-row["score"], row["page_index"]))
