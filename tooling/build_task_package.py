#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from task_package_builder import build_task_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a task package from project context and requirement text.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--vault-root", default=None)
    parser.add_argument("--note-path", default=None)
    parser.add_argument("--dev-doc-path", default=None)
    parser.add_argument("--memory-root", default=None)
    parser.add_argument("--task-slug", default=None)
    args = parser.parse_args()

    system_root = Path(__file__).resolve().parent.parent
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else None
    result = build_task_package(
        system_root=system_root,
        project=args.project,
        requirement=args.requirement,
        slug=args.slug,
        output_root=output_root,
        runtime_root=Path(args.runtime_root).expanduser().resolve() if args.runtime_root else None,
        vault_root=Path(args.vault_root).expanduser().resolve() if args.vault_root else None,
        note_path=args.note_path,
        dev_doc_path=Path(args.dev_doc_path).expanduser().resolve() if args.dev_doc_path else None,
        memory_root=Path(args.memory_root).expanduser().resolve() if args.memory_root else None,
        task_slug=args.task_slug,
    )
    print(result.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
