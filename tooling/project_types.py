#!/usr/bin/env python3
"""Project-type discovery.

Scans `project-types/` for directories with a `README.md` and returns a
machine-readable list of available project types: name, description (first
heading paragraph from README), rules (list from rules.md), pitfalls (list
from pitfalls.md).

CLI mode: `python3 tooling/project_types.py --list`
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def list_project_types(system_root: Path) -> list[dict[str, Any]]:
    """Return a list of available project types with metadata."""
    types_dir = system_root / "project-types"
    if not types_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for entry in sorted(types_dir.iterdir()):
        if not entry.is_dir():
            continue
        readme = entry / "README.md"
        if not readme.exists():
            continue

        name = entry.name
        description = _readme_description(readme)
        rules = _bullet_list(entry / "rules.md") if (entry / "rules.md").exists() else []
        pitfalls = _bullet_list(entry / "pitfalls.md") if (entry / "pitfalls.md").exists() else []

        results.append({
            "name": name,
            "description": description,
            "rules": rules,
            "pitfalls": pitfalls,
        })
    return results


def project_type_names(system_root: Path) -> list[str]:
    return [t["name"] for t in list_project_types(system_root)]


def project_type_exists(name: str, system_root: Path) -> bool:
    return name in project_type_names(system_root)


def _readme_description(path: Path) -> str:
    """Extract the first non-empty paragraph after the first `## ` heading."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_heading = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and not in_heading:
            in_heading = True
            continue
        if not in_heading:
            continue
        if not stripped:
            if collected:
                break
            continue
        collected.append(stripped)
        if len(" ".join(collected)) >= 120:
            break
    return " ".join(collected)


def _bullet_list(path: Path) -> list[str]:
    """Extract numbered or bullet items from a markdown file."""
    items: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        # numbered: "1. text" or bullet: "- text"
        if (stripped.startswith("- ") or
            (len(stripped) > 2 and stripped[0].isdigit() and stripped[1:].startswith(". "))):
            # Remove the prefix
            prefix_end = stripped.index(" ") + 1
            items.append(stripped[prefix_end:])
    return items


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    import json

    parser = argparse.ArgumentParser(description="List available Maestro project types.")
    parser.add_argument("--list", action="store_true", default=True, help="List available project types.")
    args = parser.parse_args(argv)

    resolved_root = system_root or Path(__file__).resolve().parent.parent
    types = list_project_types(resolved_root)

    text = json.dumps(types, ensure_ascii=False, indent=2)
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
