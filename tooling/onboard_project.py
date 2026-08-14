#!/usr/bin/env python3
"""Self-serve project onboarding.

Two modes:

  Interactive (default — just run it)
      $ bin/onboard-project.sh
      → prompts for project slug, summary, and project type with a pick-list.

  Batch (all arguments given)
      $ bin/onboard-project.sh --project my-app --summary "..." --project-type uniapp-mini-program
      → no prompts, ideal for scripts and CI.

Under the hood the Python API (`onboard_project()`) is always non-interactive.
"""
from __future__ import annotations

import argparse
import json
import sys
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
    repo_root: Path | None = None,
) -> JsonDict:
    """Run the full onboarding flow. Returns a readiness report.

    All parameters are required — this is the programmatic API. For an
    interactive prompt-based experience use the CLI (`main()`).
    """

    # 1. Register the project shell (canonical .md files from templates)
    register_project(
        system_root=system_root,
        project=project,
        summary=summary,
        project_type=project_type,
        force=force,
        repo_root=repo_root,
    )

    project_dir = system_root / "projects" / project

    # 2. Generate starter playbook.json
    playbook_path = project_dir / "playbook.json"
    if not playbook_path.exists() or force:
        playbook: JsonDict = {}
        if project_type:
            playbook["project_type"] = project_type
        playbook["guidance"] = []
        playbook["routing"] = {
            "fast_path_signals": [],
            "risk_rules": [],
            "risky_paths": [],
        }
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


# ── interactive prompts ──────────────────────────────────────────────


def _prompt(prompt_text: str, default: str = "") -> str:
    """Print a prompt, read a line from stdin, return stripped input."""
    if default:
        prompt_text = f"{prompt_text} [{default}]: "
    else:
        prompt_text = f"{prompt_text}: "
    try:
        return input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(1)


def _pick_project_type(system_root: Path) -> str | None:
    """Show a numbered list of project types and let the user pick one."""
    types = list_project_types(system_root)
    if not types:
        print("No project types found — proceeding without a type.\n")
        return None

    print("\nAvailable project types:\n")
    for i, t in enumerate(types, 1):
        print(f"  {i}. {t['name']}")
        print(f"     {t['description']}")
        print()

    print("  s. skip — proceed without a project type")
    print()

    while True:
        choice = _prompt("Choose", "1")
        if choice.lower() == "s":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(types):
                return types[idx]["name"]
        except ValueError:
            pass
        print(f"  Please enter 1–{len(types)} or 's' to skip.")


def _interactive_onboard(system_root: Path, force: bool = False) -> int:
    """Prompt-driven onboarding — no CLI arguments needed."""

    print("\n🛠  Maestro — New Project Onboarding\n")

    # 1. project slug
    while True:
        slug = _prompt("Project slug", "(kebab-case, e.g. my-app)")
        if not slug:
            print("  Slug is required.")
            continue
        if " " in slug or any(c.isupper() for c in slug):
            print("  Use kebab-case (lowercase, hyphens, no spaces).")
            continue
        # Quick uniqueness check
        if (system_root / "projects" / slug).exists() and not force:
            print(f"  Project '{slug}' already exists. Use --force to overwrite.")
            continue
        break

    # 2. summary
    while True:
        summary = _prompt("One-sentence summary")
        if not summary:
            print("  Summary is required.")
            continue
        break

    # 3. project type (optional, with pick-list)
    project_type = _pick_project_type(system_root)

    repo_root_text = _prompt("Business repository root (optional)")
    repo_root = Path(repo_root_text).expanduser() if repo_root_text else None

    print()

    # 4. run
    report = onboard_project(
        system_root=system_root,
        project=slug,
        summary=summary,
        project_type=project_type,
        force=force,
        repo_root=repo_root,
    )

    _print_report(report)
    return 0 if report["valid"] else 1


def _print_report(report: JsonDict) -> None:
    """Print a friendly readiness summary."""
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


# ── CLI ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Onboard a new project into Maestro — interactive by default."
    )
    parser.add_argument("--project", default=None, help="Project slug (kebab-case).")
    parser.add_argument("--summary", default=None, help="One-sentence project summary.")
    parser.add_argument("--project-type", default=None, help="Project-type hint, e.g. uniapp-mini-program.")
    parser.add_argument("--repo-root", default=None, help="Business repository root where AGENTS.md is managed.")
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

    # If all required args are given, run non-interactively (batch mode).
    if args.project and args.summary:
        report = onboard_project(
            system_root=resolved_root,
            project=args.project,
            summary=args.summary,
            project_type=args.project_type,
            force=args.force,
            repo_root=Path(args.repo_root) if args.repo_root else None,
        )
        _print_report(report)
        if stdout_path is not None:
            stdout_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["valid"] else 1

    # Otherwise, interactive mode.
    return _interactive_onboard(resolved_root, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
