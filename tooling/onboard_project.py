#!/usr/bin/env python3
"""Self-serve project onboarding.

Guided CLI that:
  1. Lists available project types (--list-types)
  2. Registers a new project shell (delegates to register_project)
  3. Generates a starter playbook.json (empty guidance, project_type set)
  4. Generates a starter business-card.json (one_liner = summary)
  5. Runs validate_project and prints a readiness report

After onboarding the project is ready for memory-read-first task work.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from business_card import generate_empty_card
from project_types import list_project_types
from register_project import register_project
from validate_project import validate_project

JsonDict = dict[str, Any]


def onboard_project(
    *,
    system_root: Path,
    project: str,
    summary: str,
    project_type: str | None = None,
    force: bool = False,
) -> JsonDict:
    """Run the full onboarding flow. Returns a readiness report."""

    # 1. Register the project shell (canonical .md files from templates)
    register_project(
        system_root=system_root,
        project=project,
        summary=summary,
        project_type=project_type,
        force=force,
    )

    project_dir = system_root / "projects" / project

    # 2. Generate starter playbook.json
    playbook_path = project_dir / "playbook.json"
    if not playbook_path.exists() or force:
        playbook: JsonDict = {}
        if project_type:
            playbook["project_type"] = project_type
        playbook["guidance"] = []
        playbook_path.write_text(
            json.dumps(playbook, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # 3. Generate starter business-card.json
    card_path = project_dir / "business-card.json"
    if not card_path.exists() or force:
        card = generate_empty_card(project, project_type)
        card["one_liner"] = summary
        card_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # 4. Run validation
    report = validate_project(system_root=system_root, project=project)
    return report


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Onboard a new project into Maestro — self-serve guided setup."
    )
    parser.add_argument("--project", required=True, help="Project slug (kebab-case).")
    parser.add_argument("--summary", required=True, help="One-sentence project summary.")
    parser.add_argument("--project-type", default=None, help="Project-type hint, e.g. uniapp-mini-program.")
    parser.add_argument("--list-types", action="store_true", help="List available project types and exit.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args(argv)

    resolved_root = system_root or Path(__file__).resolve().parent.parent

    if args.list_types:
        types = list_project_types(resolved_root)
        if not types:
            print("No project types found.")
        else:
            for t in types:
                print(f"  {t['name']}")
                print(f"    {t['description']}")
                if t["rules"]:
                    for r in t["rules"]:
                        print(f"    - rule: {r}")
                if t["pitfalls"]:
                    for p in t["pitfalls"]:
                        print(f"    - pitfall: {p}")
                print()
        return 0

    report = onboard_project(
        system_root=resolved_root,
        project=args.project,
        summary=args.summary,
        project_type=args.project_type,
        force=args.force,
    )

    # Print a friendly readiness summary
    print(f"\n{'✅' if report['valid'] else '⚠️'}  Project '{report['project']}' onboarded.\n")
    for check, status in report["checks"].items():
        icon = "✅" if status == "ok" else ("⚠️" if status.startswith("missing") else "❌")
        print(f"  {icon} {check}: {status}")
    if report["issues"]:
        print(f"\n📋 Issues ({len(report['issues'])}):")
        for issue in report["issues"]:
            print(f"  - {issue}")
    else:
        print("\n🎉 All checks passed. Ready for memory-read-first task work.")
    print()

    if stdout_path is not None:
        stdout_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
