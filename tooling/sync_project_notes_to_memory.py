#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from sync_obsidian_to_memory import sync_note


def list_candidate_notes(topic_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in topic_dir.glob("*.md")
            if path.is_file()
        ],
        key=lambda item: (item.stat().st_mtime, item.name),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync the latest or recent Obsidian write-back notes for one project into AI efficiency system memory."
    )
    parser.add_argument("--vault-root", required=True, help="Obsidian vault root directory")
    parser.add_argument("--project", required=True, help="Project slug, e.g. example-wxapp")
    parser.add_argument(
        "--topic-dir",
        default=None,
        help="Relative Obsidian topic dir; defaults to project-notes/<project>",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="How many most recent notes to sync. Default: 1",
    )
    parser.add_argument("--memory-root", default=None, help="AI efficiency system root; defaults to script ../../")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    vault_root = Path(args.vault_root).expanduser().resolve()
    memory_root = Path(args.memory_root).expanduser().resolve() if args.memory_root else script_dir.parent
    topic_rel = args.topic_dir or f"project-notes/{args.project}"
    topic_dir = (vault_root / topic_rel).resolve()
    if not topic_dir.exists():
        raise SystemExit(f"Topic directory not found: {topic_dir}")

    candidates = list_candidate_notes(topic_dir)
    if not candidates:
        raise SystemExit(f"No markdown notes found under: {topic_dir}")

    count = max(1, args.count)
    synced = []
    for path in candidates[:count]:
        note_rel = path.relative_to(vault_root).as_posix()
        output_path, index_path = sync_note(
            vault_root=vault_root,
            note_path=note_rel,
            project=args.project,
            memory_root=memory_root,
        )
        synced.append((note_rel, output_path, index_path))

    for note_rel, output_path, index_path in synced:
        print(f"Synced `{note_rel}` -> {output_path}")
        print(f"Updated index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
