"""Machine-readable Change Spec artifacts and their implementation-entry gate."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from register_project import seed_project_baseline as _seed_project_baseline


GOVERNANCE_TIERS = {"L0", "L1", "L2", "L3"}
PROFILES = {"frontend", "backend", "data-platform", "cross-cutting"}
_TASK_PACKAGE_ROOT = Path("runtime") / "task-packages"


def get_project_baseline(*, system_root: Path, project: str) -> dict[str, Any]:
    project_dir = _project_dir(system_root, project)
    path = project_dir / "spec" / "project-baseline.md"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "project": project,
        "path": str(path),
        "exists": path.exists(),
        "status": _extract_baseline_status(content),
        "content": content,
    }


def seed_project_baseline(*, system_root: Path, project: str) -> Path:
    return _seed_project_baseline(system_root=system_root, project=project)


def create_change_spec(
    *,
    system_root: Path,
    project: str,
    package_dir: Path,
    title: str,
    requirement: str,
    governance_tier: str,
    profile: str,
    allowed_files: list[dict[str, str]],
    allowed_behaviors: list[str],
    non_goals: list[str],
    acceptance_criteria: list[str],
    tasks: list[dict[str, Any]],
    verification: dict[str, list[str]],
    open_questions: list[str] | None = None,
    safe_assumptions: list[str] | None = None,
    technical_approach: str | None = None,
) -> dict[str, Any]:
    _project_dir(system_root, project)
    resolved_package_dir = _task_package_dir(system_root, package_dir)
    package = _load_package(resolved_package_dir)
    package_project = package.get("project")
    if package_project != project:
        raise ValueError(f"Task package belongs to project {package_project}, not {project}")
    if governance_tier not in GOVERNANCE_TIERS:
        raise ValueError(f"Unsupported governance tier: {governance_tier}")
    if profile not in PROFILES:
        raise ValueError(f"Unsupported Spec profile: {profile}")

    baseline = get_project_baseline(system_root=system_root, project=project)
    spec = {
        "schema_version": 1,
        "project": project,
        "title": _require_text(title, "title"),
        "created_at": _timestamp(),
        "status": "draft",
        "governance_tier": governance_tier,
        "profile": profile,
        "task_package": str(resolved_package_dir),
        "project_baseline": {
            "path": baseline["path"],
            "exists": baseline["exists"],
            "status": baseline["status"],
        },
        "requirement": _require_text(requirement, "requirement"),
        "facts_and_sources": package.get("sources", []),
        "allowed_files": _normalise_allowed_files(allowed_files),
        "allowed_behaviors": _normalise_text_list(allowed_behaviors, "allowed_behaviors"),
        "non_goals": _normalise_text_list(non_goals, "non_goals"),
        "open_questions": _normalise_text_list(open_questions or [], "open_questions", allow_empty=True),
        "safe_assumptions": _normalise_text_list(safe_assumptions or [], "safe_assumptions", allow_empty=True),
        "technical_approach": _require_text(technical_approach or "", "technical_approach"),
        "scope_expansion_trigger": "Any new file, behavior, dependency, interface, or fallback requires a new explicit approval.",
        "tasks": _normalise_tasks(tasks),
        "acceptance_criteria": _normalise_text_list(acceptance_criteria, "acceptance_criteria"),
        "verification": _normalise_verification(verification),
        "findings_outside_scope": [],
        "approval": None,
    }
    spec_path = resolved_package_dir / "spec.json"
    markdown_path = resolved_package_dir / "spec.md"
    _write_spec(spec_path, markdown_path, spec)
    _update_package_spec_state(
        system_root=system_root,
        package_dir=resolved_package_dir,
        spec_path=spec_path,
        status=spec["status"],
    )
    return {"spec_path": str(spec_path), "markdown_path": str(markdown_path), "spec": spec}


def approve_change_spec(*, system_root: Path, spec_path: Path, approver: str, source_reference: str) -> dict[str, Any]:
    resolved_spec_path = _spec_path(system_root, spec_path)
    spec = _load_spec(resolved_spec_path)
    blockers = _gate_blockers(system_root=system_root, spec=spec, require_approval=False)
    if blockers:
        raise ValueError("Change Spec cannot be approved: " + "; ".join(blockers))
    spec["approval"] = {
        "approver": _require_text(approver, "approver"),
        "approved_at": _timestamp(),
        "source_reference": _require_text(source_reference, "source_reference"),
    }
    spec["status"] = "approved_for_implementation"
    markdown_path = resolved_spec_path.with_suffix(".md")
    _write_spec(resolved_spec_path, markdown_path, spec)
    _update_package_spec_state(
        system_root=system_root,
        package_dir=Path(spec["task_package"]),
        spec_path=resolved_spec_path,
        status=spec["status"],
    )
    return {"spec_path": str(resolved_spec_path), "markdown_path": str(markdown_path), "spec": spec, "approval": spec["approval"]}


def spec_gate(*, system_root: Path, spec_path: Path) -> dict[str, Any]:
    resolved_spec_path = _spec_path(system_root, spec_path)
    spec = _load_spec(resolved_spec_path)
    blockers = _gate_blockers(system_root=system_root, spec=spec, require_approval=True)
    warnings: list[str] = []
    baseline_status = spec.get("project_baseline", {}).get("status", "missing")
    if baseline_status.lower().startswith("initial registration draft"):
        warnings.append("project baseline is an initial draft; use only its explicitly evidenced rules")
    return {
        "passed": not blockers,
        "spec_path": str(resolved_spec_path),
        "status": spec.get("status", "unknown"),
        "blockers": blockers,
        "warnings": warnings,
    }


def _gate_blockers(*, system_root: Path, spec: dict[str, Any], require_approval: bool) -> list[str]:
    blockers: list[str] = []
    project = spec.get("project")
    if not isinstance(project, str) or not project:
        return ["missing project"]
    try:
        _project_dir(system_root, project)
    except ValueError:
        return [f"unknown project: {project}"]
    baseline_path = Path(str(spec.get("project_baseline", {}).get("path", "")))
    if not baseline_path.is_file():
        blockers.append("missing project baseline")
    for key in ("requirement", "technical_approach"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            blockers.append(f"missing {key.replace('_', ' ')}")
    for key in ("allowed_files", "allowed_behaviors", "non_goals", "tasks", "acceptance_criteria"):
        if not isinstance(spec.get(key), list) or not spec[key]:
            blockers.append(f"missing {key.replace('_', ' ')}")
    verification = spec.get("verification")
    if not isinstance(verification, dict) or not any(verification.get(key) for key in ("automated", "manual", "regression")):
        blockers.append("missing verification plan")
    if spec.get("open_questions"):
        blockers.append("unresolved open questions")
    if require_approval:
        approval = spec.get("approval")
        if not isinstance(approval, dict) or not all(isinstance(approval.get(key), str) and approval[key].strip() for key in ("approver", "approved_at", "source_reference")):
            blockers.append("missing explicit approval")
        elif spec.get("status") != "approved_for_implementation":
            blockers.append("status is not approved_for_implementation")
    return blockers


def _project_dir(system_root: Path, project: str) -> Path:
    project_dir = Path(system_root).resolve() / "projects" / project
    if not project_dir.is_dir():
        raise ValueError(f"Unknown project: {project}")
    return project_dir


def _task_package_dir(system_root: Path, package_dir: Path) -> Path:
    resolved = Path(package_dir).expanduser().resolve()
    root = Path(system_root).resolve() / _TASK_PACKAGE_ROOT
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Task package must be under {root}") from exc
    return resolved


def _spec_path(system_root: Path, spec_path: Path) -> Path:
    resolved = Path(spec_path).expanduser().resolve()
    _task_package_dir(system_root, resolved.parent)
    if resolved.name != "spec.json" or not resolved.is_file():
        raise ValueError(f"Change Spec does not exist: {resolved}")
    return resolved


def _load_package(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "package.json"
    if not path.is_file():
        raise ValueError(f"Task package does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid task package JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid task package JSON: {path}")
    return payload


def _load_spec(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Change Spec JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid Change Spec JSON: {path}")
    return payload


def _normalise_allowed_files(value: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("allowed_files must contain at least one file")
    normalised = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("allowed_files entries must be objects")
        normalised.append({"path": _require_text(item.get("path", ""), "allowed_files.path"), "reason": _require_text(item.get("reason", ""), "allowed_files.reason")})
    return normalised


def _normalise_text_list(value: list[str], label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{label} must contain at least one item")
    return [_require_text(item, label) for item in value]


def _normalise_tasks(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("tasks must contain at least one item")
    tasks = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("tasks entries must be objects")
        files = _normalise_text_list(item.get("allowed_files", []), "tasks.allowed_files")
        criteria = _normalise_text_list(item.get("acceptance_criteria", []), "tasks.acceptance_criteria")
        tasks.append({
            "id": _require_text(item.get("id", ""), "tasks.id"),
            "outcome": _require_text(item.get("outcome", ""), "tasks.outcome"),
            "allowed_files": files,
            "acceptance_criteria": criteria,
            "status": "not_started",
        })
    return tasks


def _normalise_verification(value: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise ValueError("verification must be an object")
    result = {key: _normalise_text_list(value.get(key, []), f"verification.{key}", allow_empty=True) for key in ("automated", "manual", "regression")}
    if not any(result.values()):
        raise ValueError("verification must contain at least one check")
    return result


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _extract_baseline_status(content: str) -> str:
    if not content:
        return "missing"
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## status":
            values = []
            for candidate in lines[index + 1 :]:
                if candidate.startswith("## "):
                    break
                stripped = candidate.strip().lstrip("- ").strip()
                if stripped:
                    values.append(stripped)
            return " ".join(values) or "available"
    return "available"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_spec(spec_path: Path, markdown_path: Path, spec: dict[str, Any]) -> None:
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_spec_markdown(spec), encoding="utf-8")


def _update_package_spec_state(*, system_root: Path, package_dir: Path, spec_path: Path, status: str) -> None:
    resolved_package_dir = _task_package_dir(system_root, package_dir)
    package_path = resolved_package_dir / "package.json"
    package = _load_package(resolved_package_dir)
    try:
        stored_path = spec_path.resolve().relative_to(Path(system_root).resolve()).as_posix()
    except ValueError:
        stored_path = str(spec_path.resolve())
    package["change_spec"] = {"path": stored_path, "exists": True, "status": status}
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_spec_markdown(spec: dict[str, Any]) -> str:
    lines = [
        f"# Change Spec: {spec['title']}", "",
        "## Contract Metadata", "",
        f"- Project: `{spec['project']}`",
        f"- Governance tier: `{spec['governance_tier']}`",
        f"- Profile: `{spec['profile']}`",
        f"- Status: `{spec['status']}`",
        f"- Project Baseline: `{spec['project_baseline']['path']}` ({spec['project_baseline']['status']})", "",
        "## Requirement", "", spec["requirement"], "",
        "## Scope", "",
    ]
    lines.extend([f"- `{item['path']}`: {item['reason']}" for item in spec["allowed_files"]])
    lines.extend(["", "### Allowed Behavior Changes", ""])
    lines.extend([f"- {item}" for item in spec["allowed_behaviors"]])
    lines.extend(["", "## Non-goals And Prohibited Changes", ""])
    lines.extend([f"- {item}" for item in spec["non_goals"]])
    lines.extend(["", "## Open Questions", ""])
    lines.extend([f"- {item}" for item in spec["open_questions"]] or ["- None."])
    lines.extend(["", "## Technical Solution Design", "", spec["technical_approach"], "", "## Task Breakdown Checklist", ""])
    for task in spec["tasks"]:
        lines.append(f"- [ ] {task['id']}: {task['outcome']}")
        lines.extend([f"  - Allowed file: `{path}`" for path in task["allowed_files"]])
    lines.extend(["", "## Acceptance Criteria", ""])
    lines.extend([f"- [ ] AC{index + 1}: {item}" for index, item in enumerate(spec["acceptance_criteria"])])
    lines.extend(["", "## Verification Plan", ""])
    for group in ("automated", "manual", "regression"):
        lines.append(f"### {group.title()}")
        lines.extend([f"- {item}" for item in spec["verification"][group]] or ["- None."])
    lines.extend(["", "## Approval", ""])
    approval = spec.get("approval")
    if approval:
        lines.extend([f"- Approver: {approval['approver']}", f"- Time: {approval['approved_at']}", f"- Source: {approval['source_reference']}"])
    else:
        lines.append("- Not approved.")
    lines.append("")
    return "\n".join(lines)
