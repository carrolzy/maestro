#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re


def register_project(
    *,
    system_root: Path,
    project: str,
    summary: str,
    project_type: str | None = None,
    force: bool = False,
) -> Path:
    _assert_valid_project_slug(project)
    project_dir = system_root / "projects" / project
    canonical_files = {
        "business_context": project_dir / "business-context.md",
        "project_override": project_dir / "project-override.md",
        "task_context": project_dir / "task-context.md",
    }

    if project_dir.exists() and not force:
        raise FileExistsError(f"Project already exists: {project_dir}")

    rendered = _render_project_files(
        templates_root=system_root / "templates",
        project=project,
        summary=summary,
        project_type=project_type,
    )

    project_dir.mkdir(parents=True, exist_ok=True)
    for key, output_path in canonical_files.items():
        output_path.write_text(rendered[key], encoding="utf-8")
    return project_dir


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register a new project shell in the local AI efficiency system.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--project-type", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    project_dir = register_project(
        system_root=resolved_system_root,
        project=args.project,
        summary=args.summary,
        project_type=args.project_type,
        force=args.force,
    )
    _write_lines([str(project_dir)], stdout_path=stdout_path)
    return 0


def _assert_valid_project_slug(project: str) -> None:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project):
        raise ValueError(f"Invalid project slug: {project}")


def _render_project_files(*, templates_root: Path, project: str, summary: str, project_type: str | None) -> dict[str, str]:
    business_template = (templates_root / "business-context.md").read_text(encoding="utf-8")
    override_template = (templates_root / "project-override.md").read_text(encoding="utf-8")
    task_template = (templates_root / "task-context.md").read_text(encoding="utf-8")

    project_type_hint = project_type or "not specified"
    business_context = _fill_template(
        business_template,
        {
            "Project in One Sentence": summary,
            "Business Goals": "- Fill in the primary business goals for this project.",
            "User Roles": "- Fill in the main user roles for this project.",
            "Core Business Objects": "- Fill in the main business objects for this project.",
            "Key Business Flows": "- Fill in the key user or system flows for this project.",
            "Page or Module Mapping": "- Fill in the main pages, modules, or surfaces for this project.",
            "Critical Rules and Boundaries": "- Fill in the most important constraints and system boundaries for this project.",
            "Interface Semantics": "- Fill in any important API, payload, or domain semantics for this project.",
            "Historical Pitfalls": "- Fill in known failure modes, regressions, or forbidden shortcuts for this project.",
        },
    )
    project_override = _fill_template(
        override_template,
        {
            "Project Terms": f"- `{project}`: fill in the project-specific terms and vocabulary.",
            "Module Responsibilities": "- Fill in the modules or files that own core responsibilities.",
            "Interface or Domain Notes": "- Fill in any project-specific interface or domain notes.",
            "Special Components or Utilities": "- Fill in any shared components, services, or utilities that matter repeatedly.",
            "Release Flow": "- Fill in the normal local verification or release commands for this project.",
            "Known Incidents and Forbidden Zones": "- Fill in known hazards, unstable areas, or forbidden implementation paths.",
        },
    )
    task_context = _fill_template(
        task_template,
        {
            "Current Task": f"Register `{project}` into the local AI efficiency system as a new project shell.",
            "Why This Task Exists": "- This project is entering the system so future work can route through project-intake and memory-read-first.",
            "Business Delta for This Task": f"- Initial registration only. Project type hint: `{project_type_hint}`.",
            "Affected Pages or Modules": "- Fill in the first high-signal pages or modules once the project has stronger local context.",
            "Constraints for This Task": "- Keep registration conservative. Add project-specific detail later through normal task work.",
            "Verification Focus": "- Verify the generated shell is complete and future requirements can reference this project slug safely.",
        },
    )

    return {
        "business_context": business_context,
        "project_override": project_override,
        "task_context": task_context,
    }


def _fill_template(template: str, section_map: dict[str, str]) -> str:
    lines = template.rstrip().splitlines()
    output_lines: list[str] = []
    for line in lines:
        output_lines.append(line)
        if line.startswith("## "):
            section_name = line[3:].strip()
            content = section_map.get(section_name)
            if content:
                output_lines.append("")
                output_lines.extend(content.splitlines())
    output_lines.append("")
    return "\n".join(output_lines)


def _write_lines(lines: list[str], *, stdout_path: Path | None) -> None:
    text = "".join(f"{line}\n" for line in lines)
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())

