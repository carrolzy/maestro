#!/usr/bin/env python3
"""Project readiness validator.

Checks that a registered project has all required artifacts and that optional
config files (playbook.json, business-card.json) are well-formed. Returns a
machine-readable report so both MCP clients and the onboarding CLI can surface
gaps before work starts.

CLI: `python3 tooling/validate_project.py --project <slug>`
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from business_card import load_and_validate_card
from playbook_schema import load_and_validate_playbook
from project_types import project_type_exists

JsonDict = dict[str, Any]

CANONICAL_FILES = ["business-context.md", "project-override.md", "task-context.md"]


def validate_project(
    *,
    system_root: Path,
    project: str,
) -> JsonDict:
    """Run all readiness checks and return a report dict.

    Checks:
      - canonical markdown files exist
      - playbook.json is present and valid (warn on missing, error on invalid)
      - business-card.json is present and valid (warn on missing, error on invalid)
      - project_type (from playbook) is a known type
    """
    project_dir = system_root / "projects" / project
    issues: list[str] = []
    checks: dict[str, str] = {}
    all_valid = True

    # 1. canonical markdown files
    missing_files = [f for f in CANONICAL_FILES if not (project_dir / f).exists()]
    if missing_files:
        checks["canonical_files"] = f"missing: {', '.join(missing_files)}"
        issues.append(checks["canonical_files"])
        all_valid = False
    else:
        checks["canonical_files"] = "ok"

    # 2. playbook
    playbook_path = project_dir / "playbook.json"
    playbook: JsonDict = {}
    if playbook_path.exists():
        playbook, errors = load_and_validate_playbook(playbook_path)
        if errors:
            checks["playbook"] = f"invalid: {'; '.join(errors)}"
            issues.append(checks["playbook"])
            all_valid = False
        else:
            checks["playbook"] = "ok"
    else:
        checks["playbook"] = "missing"
        issues.append("playbook.json not found (guidance will be generic)")

    # 3. business card
    card_path = project_dir / "business-card.json"
    if card_path.exists():
        _, errors = load_and_validate_card(card_path)
        if errors:
            checks["business_card"] = f"invalid: {'; '.join(errors)}"
            issues.append(checks["business_card"])
            all_valid = False
        else:
            checks["business_card"] = "ok"
    else:
        checks["business_card"] = "missing"
        issues.append("business-card.json not found (machine-readable descriptor missing)")

    # 4. project type
    playbook_type = playbook.get("project_type") if isinstance(playbook.get("project_type"), str) else None
    if playbook_type:
        if project_type_exists(playbook_type, system_root):
            checks["project_type_known"] = "ok"
        else:
            checks["project_type_known"] = f"unknown: {playbook_type!r}"
            issues.append(checks["project_type_known"])
            # non-fatal: missing type from registry is a warning, not invalid
    else:
        checks["project_type_known"] = "not set"

    return {
        "project": project,
        "valid": all_valid,
        "checks": checks,
        "issues": issues,
    }


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Maestro project readiness.")
    parser.add_argument("--project", required=True, help="Project slug to validate.")
    args = parser.parse_args(argv)

    resolved_root = system_root or Path(__file__).resolve().parent.parent
    project_dir = resolved_root / "projects" / args.project
    if not project_dir.exists():
        text = json.dumps(
            {"project": args.project, "valid": False, "checks": {}, "issues": [f"project directory not found: {project_dir}"]},
            ensure_ascii=False,
            indent=2,
        )
        if stdout_path is not None:
            stdout_path.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 1

    report = validate_project(system_root=resolved_root, project=args.project)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
