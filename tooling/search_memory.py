#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


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

    tokens = _tokenize(query or "")
    project_slugs = _selected_projects(projects_root=projects_root, project=project, tokens=tokens, limit=max_projects)

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

    matched_patterns = _match_entries(
        root=system_root / "memory" / "patterns",
        base_root=system_root,
        tokens=tokens,
        limit=max_matches,
    )
    matched_rules = _match_entries(
        root=system_root / "memory" / "rules",
        base_root=system_root,
        tokens=tokens,
        limit=max_matches,
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


def _selected_projects(*, projects_root: Path, project: str | None, tokens: list[str], limit: int) -> list[str]:
    if project:
        return [project]

    slugs = sorted(path.name for path in projects_root.iterdir() if path.is_dir()) if projects_root.exists() else []
    if not tokens:
        return slugs[:limit]

    scored = []
    for slug in slugs:
        text = " ".join(
            [
                slug,
                _read_optional_text(projects_root / slug / "business-context.md"),
                _read_optional_text(projects_root / slug / "project-override.md"),
            ]
        )
        score = _score_text(tokens=tokens, text=text)
        scored.append((score, slug))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [slug for _, slug in scored[:limit]]


def _recent_case_entries(*, system_root: Path, project: str, limit: int) -> list[dict[str, str]]:
    case_dir = system_root / "memory" / "projects" / project / "cases"
    if not case_dir.exists():
        return []
    paths = sorted(case_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    entries = []
    for path in paths:
        entries.append(
            {
                "project": project,
                "slug": path.stem,
                "path": path.relative_to(system_root).as_posix(),
            }
        )
    return entries


def _recent_case_entries_all_projects(*, system_root: Path, limit: int) -> list[dict[str, str]]:
    memory_projects_root = system_root / "memory" / "projects"
    if not memory_projects_root.exists():
        return []

    scored = []
    for project_dir in sorted(path for path in memory_projects_root.iterdir() if path.is_dir()):
        case_dir = project_dir / "cases"
        if not case_dir.exists():
            continue
        for path in case_dir.glob("*.md"):
            scored.append((path.stat().st_mtime, project_dir.name, path))

    scored.sort(key=lambda item: (-item[0], item[1], item[2].name))
    entries = []
    for _, project, path in scored[:limit]:
        entries.append(
            {
                "project": project,
                "slug": path.stem,
                "path": path.relative_to(system_root).as_posix(),
            }
        )
    return entries


def _match_entries(*, root: Path, base_root: Path, tokens: list[str], limit: int) -> list[dict[str, str]]:
    if not root.exists() or not tokens:
        return []

    scored = []
    for path in sorted(root.glob("*.md")):
        text = _read_optional_text(path)
        score = _score_text(tokens=tokens, text=f"{path.stem}\n{text}")
        if score > 0:
            scored.append((score, path))
    scored.sort(key=lambda item: (-item[0], item[1].name))

    entries = []
    for _, path in scored[:limit]:
        entries.append(
            {
                "slug": path.stem,
                "path": path.relative_to(base_root).as_posix(),
            }
        )
    return entries


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    seen = []
    for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", lowered):
        if token and token not in seen:
            seen.append(token)
    return seen


def _score_text(*, tokens: list[str], text: str) -> int:
    lowered = text.lower()
    return sum(1 for token in tokens if token in lowered)


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


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
