#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from register_project import seed_project_baseline


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a missing Project Baseline Spec without rewriting project cards.")
    parser.add_argument("--project", required=True)
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    baseline_path = seed_project_baseline(system_root=resolved_system_root, project=args.project)
    _write_line(str(baseline_path), stdout_path=stdout_path)
    return 0


def _write_line(line: str, *, stdout_path: Path | None) -> None:
    text = f"{line}\n"
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
