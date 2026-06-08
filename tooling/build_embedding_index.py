#!/usr/bin/env python3
"""Build the semantic embedding index for memory search.

This is the optional second layer of memory search (the first, BM25, always
works with zero setup). It computes an embedding vector for every memory
document — patterns, rules, and project cases — and writes them to
memory/.embedding_cache.json. search_memory then blends BM25 with cosine
similarity for cross-language semantic recall.

Embeddings are fetched from any OpenAI-compatible /v1/embeddings endpoint,
configured via environment variables:

    AI_EFF_EMBED_BASE_URL   e.g. https://api.openai.com/v1  (default)
    AI_EFF_EMBED_API_KEY    your API key (required)
    AI_EFF_EMBED_MODEL      e.g. text-embedding-3-small     (default)

Usage:
    AI_EFF_EMBED_API_KEY=sk-... python3 tooling/build_embedding_index.py
    AI_EFF_EMBED_API_KEY=sk-... python3 tooling/build_embedding_index.py --dry-run

Uses only stdlib (urllib) — no openai package needed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

_TOOLING = Path(__file__).resolve().parent
if str(_TOOLING) not in sys.path:
    sys.path.insert(0, str(_TOOLING))

from embedding_index import EmbeddingIndex


def _collect_memory_docs(system_root: Path) -> list[Path]:
    """All memory documents to embed: patterns, rules, and project cases."""
    paths: list[Path] = []
    mem = system_root / "memory"
    paths.extend(sorted((mem / "patterns").glob("*.md")))
    paths.extend(sorted((mem / "rules").glob("*.md")))
    projects = mem / "projects"
    if projects.exists():
        for proj in sorted(p for p in projects.iterdir() if p.is_dir()):
            paths.extend(sorted((proj / "cases").glob("*.md")))
    return paths


def _make_embed_fn(base_url: str, api_key: str, model: str):
    """Return a text → vector function backed by an OpenAI-compatible API."""
    endpoint = base_url.rstrip("/") + "/embeddings"

    def embed(text: str) -> list[float]:
        # Truncate very long docs — embedding models cap input tokens.
        payload = json.dumps({"model": model, "input": text[:8000]}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["data"][0]["embedding"]

    return embed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the memory embedding index.")
    parser.add_argument("--system-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--dry-run", action="store_true", help="List documents that would be embedded, without calling the API.")
    args = parser.parse_args(argv)

    system_root = Path(args.system_root).resolve()
    docs = _collect_memory_docs(system_root)

    if not docs:
        print("No memory documents found — nothing to embed.")
        return 0

    if args.dry_run:
        print(f"Would embed {len(docs)} document(s):")
        for p in docs:
            print(f"  {p.relative_to(system_root).as_posix()}")
        return 0

    api_key = os.environ.get("AI_EFF_EMBED_API_KEY")
    if not api_key:
        print("ERROR: AI_EFF_EMBED_API_KEY is not set.", file=sys.stderr)
        print("Set it (and optionally AI_EFF_EMBED_BASE_URL / AI_EFF_EMBED_MODEL) and retry.", file=sys.stderr)
        return 1

    base_url = os.environ.get("AI_EFF_EMBED_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_EFF_EMBED_MODEL", "text-embedding-3-small")

    embed_fn = _make_embed_fn(base_url, api_key, model)
    index = EmbeddingIndex()

    print(f"Embedding {len(docs)} document(s) via {base_url} ({model})...")
    ok = 0
    for p in docs:
        try:
            index.build_index([p], embed_fn)
            ok += 1
            print(f"  ✓ {p.relative_to(system_root).as_posix()}")
        except (urllib.error.URLError, KeyError, OSError) as exc:
            print(f"  ✗ {p.relative_to(system_root).as_posix()} — {exc}", file=sys.stderr)

    cache_path = system_root / "memory" / ".embedding_cache.json"
    index.save(cache_path)
    print(f"\nWrote {ok}/{len(docs)} embeddings to {cache_path.relative_to(system_root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
