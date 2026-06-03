#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from sync_obsidian_to_memory import sync_note

REQUIRED_NOTE_SECTIONS = [
    "Request",
    "Context Used",
    "Implementation",
    "Verification",
    "Risks / Follow-up",
    "File References",
]


def writeback_and_sync_memory(
    *,
    vault_root: Path,
    note_path: str,
    project: str,
    source_file: Path,
    memory_root: Path | None = None,
    project_root: Path | None = None,
    slug: str | None = None,
    append: bool = False,
    validate_note_sections: bool = True,
) -> tuple[Path, Path]:
    script_dir = Path(__file__).resolve().parent
    vault_root = Path(vault_root).expanduser().resolve()
    memory_root = Path(memory_root).expanduser().resolve() if memory_root else script_dir.parent
    project_root = Path(project_root).expanduser().resolve() if project_root else memory_root
    source_file = Path(source_file).expanduser().resolve()
    if not source_file.exists():
        raise FileNotFoundError(f"Source markdown not found: {source_file}")
    _assert_known_project(project_root=project_root, project=project)

    target_path = (vault_root / note_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_content = source_file.read_text(encoding="utf-8").rstrip() + "\n"
    if validate_note_sections:
        _assert_required_sections(source_content)

    if append and target_path.exists():
        previous = target_path.read_text(encoding="utf-8").rstrip()
        content = previous + "\n\n" + source_content
    else:
        content = source_content

    target_path.write_text(content, encoding="utf-8")
    output_path, index_path = sync_note(
        vault_root=vault_root,
        note_path=note_path,
        project=project,
        memory_root=memory_root,
        slug=slug,
    )
    return output_path, index_path


def _assert_known_project(*, project_root: Path, project: str) -> None:
    project_dir = project_root / "projects" / project
    if not project_dir.exists():
        raise ValueError(f"Unknown project: {project}")


def _assert_required_sections(markdown: str) -> None:
    missing_sections = [section for section in REQUIRED_NOTE_SECTIONS if f"## {section}" not in markdown and f"# {section}" not in markdown]
    if missing_sections:
        missing_text = ", ".join(missing_sections)
        raise ValueError(f"Source markdown missing required sections: {missing_text}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a markdown note into Obsidian and immediately sync it into project memory."
    )
    parser.add_argument("--vault-root", required=True, help="Obsidian vault root directory")
    parser.add_argument("--note-path", required=True, help="Relative note path inside the vault")
    parser.add_argument("--project", required=True, help="Project slug, e.g. example-wxapp")
    parser.add_argument("--source-file", required=True, help="Markdown source file to write into Obsidian")
    parser.add_argument("--memory-root", default=None, help="AI efficiency system root; defaults to script ../../")
    parser.add_argument("--slug", default=None, help="Optional output slug override")
    parser.add_argument("--append", action="store_true", help="Append to the existing note instead of overwrite")
    args = parser.parse_args()

    vault_root = Path(args.vault_root).expanduser().resolve()
    output_path, index_path = writeback_and_sync_memory(
        vault_root=vault_root,
        note_path=args.note_path,
        project=args.project,
        source_file=Path(args.source_file),
        memory_root=Path(args.memory_root).expanduser().resolve() if args.memory_root else None,
        slug=args.slug,
        append=args.append,
    )

    print(f"Wrote note to: {vault_root / args.note_path}")
    print(f"Synced memory case to: {output_path}")
    print(f"Updated index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
