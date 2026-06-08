#!/usr/bin/env python3
"""Lightweight embedding index for semantic memory search.

Stores document embedding vectors as a flat JSON file so that the search path
can do a hybrid BM25 + cosine-similarity ranking without pulling in numpy,
PyTorch, or any ML runtime.

Embedding *computation* is deliberately left outside Maestro — a user or
external script calls an embedding API (OpenAI, local model, etc.) and feeds
the vectors into build_index(). Once built, the index is a pure-data JSON file
that lives alongside the memory documents.

Design:
  - Vectors are list[float], serialized as JSON arrays.
  - Cosine similarity = dot(A,B) / (|A| * |B|), pure-Python math.
  - Index file: memory/.embedding_cache.json → {doc_path: vector, ...}
  - Zero dependencies beyond stdlib.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors.

    Returns 0.0 when either vector is all-zeros (degenerate).
    """
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = _norm(a)
    nb = _norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class EmbeddingIndex:
    """In-memory embedding index with JSON persistence.

    Usage::

        idx = EmbeddingIndex()
        # Build from external embedding function
        idx.build_index(
            paths=[Path("memory/patterns/a.md"), Path("memory/patterns/b.md")],
            embed_fn=lambda text: openai_embed(text),  # user-provided
        )
        idx.save(Path("memory/.embedding_cache.json"))

        # Later, at search time:
        idx = EmbeddingIndex.load(Path("memory/.embedding_cache.json"))
        hits = idx.search(query_vec, top_k=5)
    """

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}

    def __len__(self) -> int:
        return len(self._vectors)

    def __bool__(self) -> bool:
        return bool(self._vectors)

    def build_index(self, paths: list[Path], embed_fn: Callable[[str], list[float]]) -> None:
        """Compute and store embedding vectors for a set of documents.

        Args:
            paths: Document paths (used as keys in the index).
            embed_fn: text → embedding vector. Called once per document.
        """
        for p in paths:
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            vec = embed_fn(text)
            if vec:
                self._vectors[p.as_posix()] = vec

    def search(self, query_vec: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        """Return the top-k document paths ranked by cosine similarity to query_vec.

        Returns list of (doc_path, similarity_score), highest first.
        """
        if not self._vectors:
            return []
        scored = [(path, cosine_similarity(query_vec, vec)) for path, vec in self._vectors.items()]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def save(self, path: Path) -> None:
        """Persist the index to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._vectors, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "EmbeddingIndex":
        """Load an index from a JSON file. Returns an empty index if missing."""
        idx = cls()
        if not path.exists():
            return idx
        try:
            idx._vectors = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            idx._vectors = {}
        return idx
