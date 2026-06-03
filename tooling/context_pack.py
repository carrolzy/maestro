#!/usr/bin/env python3
"""Emit a model-agnostic task context pack for any LLM prompt.

For runtimes without MCP or skills support (e.g. raw Gemini / DeepSeek API
calls), this builds a task package and prints its `package.md` — a
self-contained briefing you can inject directly into a model's prompt.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from task_package_builder import build_task_package


def build_context_pack(
    *,
    system_root: Path,
    project: str,
    requirement: str,
    slug: str | None = None,
) -> str:
    with tempfile.TemporaryDirectory(prefix="maestro-context-pack-") as tmp:
        result = build_task_package(
            system_root=system_root,
            project=project,
            requirement=requirement,
            slug=slug,
            output_root=Path(tmp),
        )
        return (result.output_dir / "package.md").read_text(encoding="utf-8")


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a model-agnostic task context pack (package.md) for any LLM prompt."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--out", default=None, help="Write to this file instead of stdout.")
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    text = build_context_pack(
        system_root=resolved_system_root,
        project=args.project,
        requirement=args.requirement,
        slug=args.slug,
    )

    target = Path(args.out) if args.out else (Path(stdout_path) if stdout_path else None)
    if target is not None:
        target.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
