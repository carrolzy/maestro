from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from pathlib import Path

from update_task_run_state import update_task_run_state
from writeback_and_sync_memory import writeback_and_sync_memory


@dataclass
class BuildTaskPackageResult:
    output_dir: Path


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "task-package"


def _read_required_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _project_context_paths(system_root: Path, project: str) -> dict[str, Path]:
    project_dir = system_root / "projects" / project
    return {
        "business_context": project_dir / "business-context.md",
        "project_override": project_dir / "project-override.md",
        "task_context": project_dir / "task-context.md",
    }


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


def _recent_case_paths(system_root: Path, project: str, limit: int = 5) -> list[Path]:
    case_dir = system_root / "memory" / "projects" / project / "cases"
    if not case_dir.exists():
        return []
    return sorted(case_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def _match_memory_files(requirement: str, paths: list[Path], system_root: Path) -> list[str]:
    lowered = requirement.lower()
    tokens = [token for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", lowered) if token]
    matches = []
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        if not tokens:
            continue
        if any(token in text for token in tokens):
            matches.append(path.relative_to(system_root).as_posix())
    return matches


def _load_playbook(system_root: Path, project: str) -> dict:
    """Load an optional, project-local guidance playbook.

    A playbook lets a concrete project inject domain-specific module hints,
    risk flags, and verification checks without hard-coding any business logic
    into the generic builder. Projects keep their own `playbook.json` under
    `projects/<project>/`; when absent the builder stays fully generic.
    """
    playbook_path = system_root / "projects" / project / "playbook.json"
    if not playbook_path.exists():
        return {}
    try:
        return json.loads(playbook_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _resolve_project_type(*, system_root: Path, project: str) -> str:
    project_type = _load_playbook(system_root, project).get("project_type")
    return project_type if isinstance(project_type, str) and project_type else "unknown"


def _apply_playbook_guidance(playbook: dict, requirement: str) -> tuple[list[dict], list[dict], dict[str, list[str]]]:
    suspected_modules: list[dict] = []
    risk_flags: list[dict] = []
    recommended_checks: dict[str, list[str]] = {
        "verification_focus": [],
        "manual_checks": [],
        "code_checks": [],
    }
    for entry in playbook.get("guidance", []):
        keywords = entry.get("keywords", [])
        if not any(keyword in requirement for keyword in keywords):
            continue
        suspected_modules.extend(entry.get("suspected_modules", []))
        risk_flags.extend(entry.get("risk_flags", []))
        checks = entry.get("recommended_checks", {})
        for key in recommended_checks:
            recommended_checks[key].extend(checks.get(key, []))
    return suspected_modules, risk_flags, recommended_checks


def build_task_package(
    *,
    system_root: Path,
    project: str,
    requirement: str,
    slug: str | None = None,
    output_root: Path | None = None,
    runtime_root: Path | None = None,
    vault_root: Path | None = None,
    note_path: str | None = None,
    dev_doc_path: Path | None = None,
    memory_root: Path | None = None,
    task_slug: str | None = None,
) -> BuildTaskPackageResult:
    project_dir = system_root / "projects" / project
    if not project_dir.exists():
        raise ValueError(f"Unknown project: {project}")

    context_paths = _project_context_paths(system_root, project)
    now = datetime.now()
    effective_slug = slug or _slugify(requirement[:60])
    dirname = f"{now:%Y-%m-%d}-{effective_slug}"
    package_root = output_root or (system_root / "runtime" / "task-packages")
    target_dir = package_root / project / dirname
    target_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "project": project,
        "requirement": requirement,
        "slug": effective_slug,
        "created_at": now.isoformat(timespec="seconds"),
        "project_type": _resolve_project_type(system_root=system_root, project=project),
    }
    sources = []
    for path in context_paths.values():
        if path.exists():
            _read_required_text(path)
            sources.append(path.relative_to(system_root).as_posix())
    payload["sources"] = sources

    business_text = _read_optional_text(context_paths["business_context"])
    override_text = _read_optional_text(context_paths["project_override"])
    task_text = _read_optional_text(context_paths["task_context"])

    payload["business_summary"] = _extract_first_non_heading_paragraph(business_text)
    payload["project_specific_rules"] = [line.strip("- ").strip() for line in override_text.splitlines() if line.startswith("- ")]
    payload["recent_cases"] = [path.relative_to(system_root).as_posix() for path in _recent_case_paths(system_root, project)]
    payload["development_documents"] = []
    if dev_doc_path is not None:
        if not dev_doc_path.exists():
            raise ValueError(f"Development document does not exist: {dev_doc_path}")
        dev_doc_text = _read_required_text(dev_doc_path)
        payload["development_documents"].append(
            {
                "path": _relative_or_absolute(dev_doc_path, system_root),
                "summary": _extract_first_non_heading_paragraph(dev_doc_text),
            }
        )

    pattern_paths = sorted((system_root / "memory" / "patterns").glob("*.md"))
    rule_paths = sorted((system_root / "memory" / "rules").glob("*.md"))
    payload["matched_patterns"] = _match_memory_files(requirement, pattern_paths, system_root)
    payload["matched_rules"] = _match_memory_files(requirement, rule_paths, system_root)
    payload["suspected_modules"] = []
    payload["recommended_checks"] = {
        "verification_focus": [],
        "manual_checks": [],
        "code_checks": [],
    }
    payload["open_questions"] = []
    payload["risk_flags"] = []

    missing_context_messages = []
    if not business_text:
        missing_context_messages.append("missing business-context.md")
    if not override_text:
        missing_context_messages.append("missing project-override.md")
    if not task_text:
        missing_context_messages.append("missing task-context.md")
    if missing_context_messages:
        payload["open_questions"].extend(missing_context_messages)
        payload["risk_flags"].extend(
            [
                {
                    "name": "missing project context",
                    "reason": ", ".join(missing_context_messages),
                }
            ]
        )

    playbook = _load_playbook(system_root, project)
    if playbook:
        suspected_modules, playbook_risk_flags, playbook_checks = _apply_playbook_guidance(playbook, requirement)
        payload["suspected_modules"] = suspected_modules
        payload["risk_flags"].extend(playbook_risk_flags)
        if any(playbook_checks.values()):
            payload["recommended_checks"] = playbook_checks
    (target_dir / "package.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_lines = [
        "# Task Package",
        "",
        "## Request",
        "",
        requirement,
        "",
        "## Project",
        "",
        project,
        "",
        "## Business Summary",
        "",
        payload["business_summary"] or "No business summary available.",
        "",
        "## Relevant Project Rules",
        "",
    ]
    markdown_lines.extend([f"- {item}" for item in payload["project_specific_rules"]] or ["- None extracted in v1."])
    markdown_lines.extend(
        [
            "",
            "## Development Technical Documents",
            "",
        ]
    )
    if payload["development_documents"]:
        for doc in payload["development_documents"]:
            markdown_lines.append(f"- `{doc['path']}`")
            if doc["summary"]:
                markdown_lines.append(f"  - {doc['summary']}")
    else:
        markdown_lines.append("- None supplied.")
    markdown_lines.extend(
        [
            "",
            "## Recent Relevant Cases",
            "",
        ]
    )
    markdown_lines.extend([f"- `{item}`" for item in payload["recent_cases"]] or ["- None found."])
    markdown_lines.extend(
        [
            "",
            "## Reusable Patterns / Standing Rules",
            "",
        ]
    )
    if payload["matched_patterns"]:
        markdown_lines.extend([f"- Pattern: `{item}`" for item in payload["matched_patterns"]])
    if payload["matched_rules"]:
        markdown_lines.extend([f"- Rule: `{item}`" for item in payload["matched_rules"]])
    if not payload["matched_patterns"] and not payload["matched_rules"]:
        markdown_lines.append("- No matches found.")
    markdown_lines.extend(
        [
            "",
            "## Suspected Modules",
            "",
        ]
    )
    if payload["suspected_modules"]:
        for module in payload["suspected_modules"]:
            markdown_lines.append(f"- `{module['module_label']}`")
            for file_path in module["project_files"]:
                markdown_lines.append(f"  - `{file_path}`")
    else:
        markdown_lines.append("- No module guidance generated.")
    markdown_lines.extend(
        [
            "",
            "## Recommended Verification",
            "",
        ]
    )
    markdown_lines.extend(
        [f"- {item}" for item in payload["recommended_checks"]["verification_focus"]] or ["- No verification focus generated."]
    )
    markdown_lines.extend(
        [f"- {item}" for item in payload["recommended_checks"]["manual_checks"]] or ["- No manual checks generated."]
    )
    markdown_lines.extend(
        [f"- {item}" for item in payload["recommended_checks"]["code_checks"]] or ["- No code checks generated."]
    )
    markdown_lines.extend(
        [
            "",
            "## Risk Flags",
            "",
        ]
    )
    markdown_lines.extend([f"- {item['name']}: {item['reason']}" for item in payload["risk_flags"]] or ["- No risk flags generated."])
    markdown_lines.extend(
        [
            "",
            "## Open Questions",
            "",
        ]
    )
    markdown_lines.extend([f"- {item}" for item in payload["open_questions"]] or ["- None."])
    markdown_lines.extend(
        [
            "",
            "## Source Files",
            "",
        ]
    )
    markdown_lines.extend([f"- `{item}`" for item in payload["sources"]] or ["- None."])
    markdown_lines.append("")
    (target_dir / "package.md").write_text("\n".join(markdown_lines), encoding="utf-8")

    if runtime_root is not None and task_slug is not None:
        update_task_run_state(
            runtime_root=runtime_root,
            project=project,
            task_slug=task_slug,
            state="packaged",
        )

    if vault_root is not None and note_path is not None:
        writeback_and_sync_memory(
            vault_root=vault_root,
            note_path=note_path,
            project=project,
            source_file=target_dir / "package.md",
            memory_root=memory_root,
            project_root=system_root,
            slug=effective_slug,
            validate_note_sections=False,
        )
        if runtime_root is not None and task_slug is not None:
            update_task_run_state(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                state="written_back",
            )
            update_task_run_state(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                state="synced",
            )
            update_task_run_state(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                state="closed",
            )
    elif runtime_root is not None and task_slug is not None:
        update_task_run_state(
            runtime_root=runtime_root,
            project=project,
            task_slug=task_slug,
            state="pending-closeout",
        )
    return BuildTaskPackageResult(output_dir=target_dir)
