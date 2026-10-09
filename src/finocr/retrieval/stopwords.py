"""A versioned function-word ablation; no financial terms or answer keywords."""

from finocr.retrieval.bm25 import tokenize


STOPWORD_VERSION = "english-function-words-v1"
# Self-contained list, frozen after development diagnostic inspection. Negation,
# financial vocabulary, company names, numeric tokens, and units remain intact.
STOPWORDS = frozenset("""
a an the and or but if as at by for from in into of on onto to with than
that this these those is are was were be been being am do does did have has had
i me my we us our ours you your yours he him his she her hers it its they them
their theirs who whom whose which what when where why how
""".split())


def tokenize_without_stopwords(text: str) -> list[str]:
    return [term for term in tokenize(text) if term not in STOPWORDS]
