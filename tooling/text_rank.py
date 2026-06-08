#!/usr/bin/env python3
"""BM25 text ranker — Okapi BM25 with CJK-aware tokenization.

Replaces the naive token-count scoring in search_memory.py with a proper
probabilistic relevance model. BM25 accounts for:

  - Term frequency (non-linear saturation: twice isn't twice as relevant)
  - Inverse document frequency (rare terms carry more signal)
  - Document length (a 50-word doc and a 5000-word doc are on a level field)

Pure Python, zero dependencies. k1=1.5 / b=0.75 are the standard Okapi defaults
and work well across document collections from 10 to 10⁵ documents.
"""
from __future__ import annotations

import math
import re
from pathlib import Path


# ── tokenization ──────────────────────────────────────────────────

_CJK = r"一-鿿"
_CJK_RUN = re.compile(f"[{_CJK}]+")
_CJK_CHAR = re.compile(f"[{_CJK}]")


def _cjk_bigrams(run: str) -> list[str]:
    """Turn a run of CJK characters into overlapping bigrams (+ unigrams).

    Chinese has no whitespace word boundaries, so a run like "登录按钮" would
    otherwise be one opaque token that only matches verbatim. Bigrams give us
    "登录", "录按", "按钮" plus the single chars — so a query "登录" matches a
    document containing "登录按钮". This is the standard cheap CJK indexing
    trick (no dictionary/segmenter needed).
    """
    chars = list(run)
    if len(chars) == 1:
        return chars
    grams = [run[i:i + 2] for i in range(len(chars) - 1)]
    # Also keep single chars so a 1-char query still matches.
    grams.extend(chars)
    return grams


def tokenize(text: str) -> list[str]:
    """Tokenize for BM25: ASCII words split on boundaries, CJK split to bigrams.

    Returns deduplicated-in-order, lowercased tokens so a query word is counted
    once per document (the standard BM25 contract) and "Login" == "login".
    CJK runs are expanded into overlapping bigrams + unigrams so Chinese phrases
    match on shared sub-spans without a word segmenter.
    """
    lowered = text.lower()
    seen: set[str] = set()
    tokens: list[str] = []

    def _add(tok: str) -> None:
        if tok and tok not in seen:
            seen.add(tok)
            tokens.append(tok)

    # Split into ASCII-alphanumeric and CJK pieces.
    for piece in re.split(r"[^0-9a-zA-Z" + _CJK + r"]+", lowered):
        if not piece:
            continue
        if _CJK_CHAR.search(piece):
            # Mixed piece may contain CJK runs and ASCII; handle each CJK run.
            pos = 0
            for m in _CJK_RUN.finditer(piece):
                # ASCII before this CJK run
                ascii_part = piece[pos:m.start()]
                if ascii_part:
                    _add(ascii_part)
                for gram in _cjk_bigrams(m.group()):
                    _add(gram)
                pos = m.end()
            tail = piece[pos:]
            if tail:
                _add(tail)
        else:
            _add(piece)
    return tokens


# ── BM25 ranker ───────────────────────────────────────────────────

class BM25Ranker:
    """Pre-computed Okapi BM25 index over a fixed document corpus.

    Build once with the corpus texts, then call score() for each query.

    Usage::

        ranker = BM25Ranker(["doc one text", "doc two text"])
        top = ranker.top_k("query text", k=5)
    """

    def __init__(self, documents: list[str], *, k1: float = 1.5, b: float = 0.75) -> None:
        if not documents:
            raise ValueError("BM25Ranker requires at least one document")
        self.k1 = k1
        self.b = b
        self._docs: list[str] = documents
        # Pre-tokenize each document.
        self._doc_tokens: list[list[str]] = [tokenize(d) for d in documents]
        # Term → how many documents contain it.
        self._df: dict[str, int] = {}
        for tokens in self._doc_tokens:
            for t in set(tokens):
                self._df[t] = self._df.get(t, 0) + 1
        self._N = len(documents)
        self._avgdl = sum(len(toks) for toks in self._doc_tokens) / self._N
        # Pre-compute IDF for every term in the corpus.
        self._idf: dict[str, float] = {t: self._compute_idf(t) for t in self._df}

    def _compute_idf(self, term: str) -> float:
        n = self._df.get(term, 0)
        return math.log((self._N - n + 0.5) / (n + 0.5) + 1.0)

    def score(self, query: str, doc_index: int) -> float:
        """BM25 score for a single document, given a raw query string."""
        if doc_index < 0 or doc_index >= self._N:
            return 0.0
        q_tokens = tokenize(query)
        if not q_tokens:
            return 0.0
        doc_tokens = self._doc_tokens[doc_index]
        doc_len = len(doc_tokens)
        # Build a term-frequency map for the document (done lazily per call).
        tf: dict[str, int] = {}
        for t in doc_tokens:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for qt in q_tokens:
            idf = self._idf.get(qt, 0.0)
            if idf == 0.0:
                continue
            f = tf.get(qt, 0)
            if f == 0:
                continue
            numerator = f * (self.k1 + 1.0)
            denominator = f + self.k1 * (1.0 - self.b + self.b * doc_len / self._avgdl)
            score += idf * numerator / denominator
        return score

    def scores(self, query: str) -> list[float]:
        """Return BM25 scores for every document in the corpus."""
        return [self.score(query, i) for i in range(self._N)]

    def top_k(self, query: str, k: int = 5, min_score: float = 0.0) -> list[tuple[int, float]]:
        """Return (doc_index, score) pairs for the top-k documents."""
        scored = [(i, self.score(query, i)) for i in range(self._N)]
        scored = [(i, s) for i, s in scored if s > min_score]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]


def bm25_from_files(paths: list[Path]) -> BM25Ranker:
    """Convenience: build a BM25Ranker from document file paths."""
    texts = [p.read_text(encoding="utf-8") if p.exists() else "" for p in paths]
    return BM25Ranker(texts)
