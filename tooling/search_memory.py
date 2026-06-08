#!/usr/bin/env python3
"""Search local project memory and reusable knowledge.

BM25 powers the text ranking; an optional embedding index at
memory/.embedding_cache.json adds semantic (cross-language) recall.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from text_rank import BM25Ranker
from embedding_index import EmbeddingIndex


def search_memory(
    *,
    system_root: Path,
    project: str | None = None,
    query: str | None = None,
    max_projects: int = 5,
    max_cases: int = 5,
    max_matches: int = 5,
) -> dict[str, object]:
    projects_root = system_root / "projects"
    if project is not None and not (projects_root / project).exists():
        raise ValueError(f"Unknown project: {project}")

    q = query or ""
    project_slugs = _selected_projects(projects_root=projects_root, project=project, query=q, limit=max_projects)

    project_cards = []
    project_override = None
    for slug in project_slugs:
        business_path = projects_root / slug / "business-context.md"
        override_path = projects_root / slug / "project-override.md"
        project_cards.append(
            {
                "slug": slug,
                "business_context": business_path.relative_to(system_root).as_posix() if business_path.exists() else None,
                "summary": _extract_first_non_heading_paragraph(_read_optional_text(business_path)),
            }
        )
        if project == slug:
            project_override = {
                "slug": slug,
                "path": override_path.relative_to(system_root).as_posix() if override_path.exists() else None,
            }

    if project is not None:
        recent_cases = _recent_case_entries(system_root=system_root, project=project, limit=max_cases)
    else:
        recent_cases = _recent_case_entries_all_projects(system_root=system_root, limit=max_cases)

    # Load the optional embedding index for semantic hybrid search.
    emb_idx = EmbeddingIndex.load(system_root / "memory" / ".embedding_cache.json")

    matched_patterns = _match_entries(
        root=system_root / "memory" / "patterns",
        base_root=system_root,
        query=q,
        limit=max_matches,
        emb_idx=emb_idx,
    )
    matched_rules = _match_entries(
        root=system_root / "memory" / "rules",
        base_root=system_root,
        query=q,
        limit=max_matches,
        emb_idx=emb_idx,
    )

    return {
        "project_cards": project_cards,
        "project_override": project_override,
        "recent_cases": recent_cases,
        "matched_patterns": matched_patterns,
        "matched_rules": matched_rules,
    }


def main(
    argv: list[str] | None = None,
    system_root: Path | None = None,
    stdout_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Search local project memory and reusable knowledge.")
    parser.add_argument("--project", default=None)
    parser.add_argument("--query", default=None)
    parser.add_argument("--max-projects", type=int, default=5)
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--max-matches", type=int, default=5)
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    result = search_memory(
        system_root=resolved_system_root,
        project=args.project,
        query=args.query,
        max_projects=max(1, args.max_projects),
        max_cases=max(1, args.max_cases),
        max_matches=max(1, args.max_matches),
    )
    _write_output(_format_output(result), stdout_path=stdout_path)
    return 0


def _selected_projects(*, projects_root: Path, project: str | None, query: str, limit: int) -> list[str]:
    if project:
        return [project]

    slugs = sorted(path.name for path in projects_root.iterdir() if path.is_dir()) if projects_root.exists() else []
    if not slugs:
        return []
    if not query:
        return slugs[:limit]

    # Build a corpus: each "document" is the concatenation of the project's
    # slug, business-context.md, and project-override.md.
    docs = [
        " ".join([s, _read_optional_text(projects_root / s / "business-context.md"),
                   _read_optional_text(projects_root / s / "project-override.md")])
        for s in slugs
    ]
    ranker = BM25Ranker(docs)
    top = ranker.top_k(query, k=limit)
    return [slugs[i] for i, _ in top]


def _recent_case_entries(*, system_root: Path, project: str, limit: int) -> list[dict[str, str]]:
    case_dir = system_root / "memory" / "projects" / project / "cases"
    if not case_dir.exists():
        return []
    paths = sorted(case_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [{"project": project, "slug": p.stem, "path": p.relative_to(system_root).as_posix()} for p in paths]


def _recent_case_entries_all_projects(*, system_root: Path, limit: int) -> list[dict[str, str]]:
    memory_projects_root = system_root / "memory" / "projects"
    if not memory_projects_root.exists():
        return []
    scored = []
    for project_dir in sorted(p for p in memory_projects_root.iterdir() if p.is_dir()):
        case_dir = project_dir / "cases"
        if not case_dir.exists():
            continue
        for path in case_dir.glob("*.md"):
            scored.append((path.stat().st_mtime, project_dir.name, path))
    scored.sort(key=lambda x: (-x[0], x[1], x[2].name))
    return [{"project": proj, "slug": p.stem, "path": p.relative_to(system_root).as_posix()} for _, proj, p in scored[:limit]]


def _match_entries(
    *, root: Path, base_root: Path, query: str, limit: int,
    emb_idx: EmbeddingIndex | None = None,
) -> list[dict[str, str]]:
    """Score markdown files with BM25. Returns ranked entries with slug + path.

    When *emb_idx* is provided, each document's final score is a weighted blend
    of its BM25 score and its embedding cosine similarity to the query, giving
    cross-language semantic recall.
    """
    if not root.exists() or not query:
        return []

    paths = sorted(root.glob("*.md"))
    if not paths:
        return []

    # \u2500\u2500 BM25 path \u2500\u2500
    docs = [f"{p.stem}\n{_read_optional_text(p)}" for p in paths]
    ranker = BM25Ranker(docs)
    bm25_scores = ranker.scores(query)
    max_bm25 = max(bm25_scores) if bm25_scores else 1.0

    # \u2500\u2500 embedding path (optional) \u2500\u2500
    # Embed the query with the same provider the index was built with, then
    # score each indexed doc by cosine similarity. Degrades to BM25-only when
    # no index exists or no embedding API key is configured.
    emb_scores: dict[str, float] = {}
    use_emb = False
    if emb_idx:
        query_vec = _embed_query(query)
        if query_vec:
            use_emb = True
            for path, _sim in emb_idx.search(query_vec, top_k=len(emb_idx)):
                emb_scores[path] = _sim

    # \u2500\u2500 hybrid sort \u2500\u2500
    scored: list[tuple[float, Path]] = []
    for i, p in enumerate(paths):
        bm25_norm = bm25_scores[i] / max_bm25 if max_bm25 > 0 else 0.0
        emb = emb_scores.get(p.as_posix(), 0.0)
        # Weight: 0.7 BM25 + 0.3 embedding (when embeddings are available).
        hybrid = 0.7 * bm25_norm + 0.3 * emb if use_emb else bm25_norm
        if hybrid > 0:
            scored.append((hybrid, p))

    scored.sort(key=lambda x: (-x[0], x[1].name))

    return [
        {"slug": p.stem, "path": p.relative_to(base_root).as_posix()}
        for _, p in scored[:limit]
    ]


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _embed_query(query: str) -> list[float] | None:
    """Embed the query via the OpenAI-compatible API (same config as the index).

    Returns None when no API key is configured or the call fails — the caller
    then falls back to BM25-only ranking. Keeps memory search fully functional
    offline; embeddings are a pure enhancement.
    """
    import os
    api_key = os.environ.get("AI_EFF_EMBED_API_KEY")
    if not api_key or not query.strip():
        return None
    import json as _json
    import urllib.request
    import urllib.error
    base_url = os.environ.get("AI_EFF_EMBED_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_EFF_EMBED_MODEL", "text-embedding-3-small")
    endpoint = base_url.rstrip("/") + "/embeddings"
    payload = _json.dumps({"model": model, "input": query[:8000]}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return data["data"][0]["embedding"]
    except (urllib.error.URLError, KeyError, OSError, ValueError):
        return None


def _extract_first_non_heading_paragraph(markdown: str) -> str:
    lines = [line.strip() for line in markdown.splitlines()]
    collected = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        collected.append(line)
        if len(" ".join(collected)) >= 120:
            break
    return " ".join(collected).strip()


def _format_output(result: dict[str, object]) -> str:
    project_cards = result["project_cards"]
    project_override = result["project_override"]
    recent_cases = result["recent_cases"]
    matched_patterns = result["matched_patterns"]
    matched_rules = result["matched_rules"]

    lines = [
        "Project Cards",
        "",
    ]
    if project_cards:
        for item in project_cards:
            lines.append(f"- {item['slug']}: {item['business_context'] or 'missing business-context.md'}")
    else:
        lines.append("- None")

    lines.extend(["", "Project Override", ""])
    if project_override:
        lines.append(f"- {project_override['slug']}: {project_override['path'] or 'missing project-override.md'}")
    else:
        lines.append("- None")

    lines.extend(["", "Recent Cases", ""])
    if recent_cases:
        for item in recent_cases:
            lines.append(f"- {item['slug']}: {item['path']}")
    else:
        lines.append("- None")

    lines.extend(["", "Matched Patterns", ""])
    if matched_patterns:
        for item in matched_patterns:
            lines.append(f"- {item['slug']}: {item['path']}")
    else:
        lines.append("- None")

    lines.extend(["", "Matched Rules", ""])
    if matched_rules:
        for item in matched_rules:
            lines.append(f"- {item['slug']}: {item['path']}")
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def _write_output(text: str, *, stdout_path: Path | None) -> None:
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
