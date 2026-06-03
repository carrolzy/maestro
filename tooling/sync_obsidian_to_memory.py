#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Optional


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "memory-note"


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def upsert_index(index_path: Path, entry_name: str) -> None:
    if index_path.exists():
      content = index_path.read_text(encoding="utf-8")
    else:
      content = "# Project Memory Index\n\n## Recent Cases\n\n"

    if entry_name in content:
      return

    marker = "## Recent Cases"
    if marker in content:
      parts = content.split(marker, 1)
      prefix = parts[0] + marker
      suffix = parts[1]
      insertion = f"\n\n- `{entry_name}`"
      updated = prefix + insertion + suffix
    else:
      updated = content.rstrip() + f"\n\n## Recent Cases\n\n- `{entry_name}`\n"

    index_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def build_output_name(source_path: Path, slug: Optional[str] = None) -> str:
    base_name = slug or slugify(source_path.stem)
    if re.match(r"^\d{4}-\d{2}-\d{2}-", source_path.stem):
        prefix = source_path.stem.split("-", 3)
        if len(prefix) >= 3:
            return f"{prefix[0]}-{prefix[1]}-{prefix[2]}-{base_name}.md"
    return f"{base_name}.md"


def sync_note(
    *,
    vault_root: Path,
    note_path: str,
    project: str,
    memory_root: Path,
    slug: Optional[str] = None,
) -> tuple[Path, Path]:
    source_path = (vault_root / note_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source note not found: {source_path}")

    content = source_path.read_text(encoding="utf-8")
    title = extract_title(content, source_path.stem)
    output_name = build_output_name(source_path, slug=slug)

    case_dir = memory_root / "memory" / "projects" / project / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / output_name

    header = [
        f"# {title}",
        "",
        "## Synced From",
        "",
        f"- `{note_path}`",
        "",
        "## Raw Note",
        "",
    ]
    output_path.write_text("\n".join(header) + content.rstrip() + "\n", encoding="utf-8")

    index_path = memory_root / "memory" / "projects" / project / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    upsert_index(index_path, output_name)
    return output_path, index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync one Obsidian write-back note into AI efficiency system memory.")
    parser.add_argument("--vault-root", required=True, help="Obsidian vault root directory")
    parser.add_argument("--note-path", required=True, help="Relative note path inside the vault")
    parser.add_argument("--project", required=True, help="Project slug, e.g. example-wxapp")
    parser.add_argument("--memory-root", default=None, help="AI efficiency system root; defaults to script ../../")
    parser.add_argument("--slug", default=None, help="Optional output slug override")
    args = parser.parse_args()

    vault_root = Path(args.vault_root).expanduser().resolve()
    source_path = (vault_root / args.note_path).resolve()
    if not source_path.exists():
        raise SystemExit(f"Source note not found: {source_path}")

    script_dir = Path(__file__).resolve().parent
    memory_root = Path(args.memory_root).expanduser().resolve() if args.memory_root else script_dir.parent
    output_path, index_path = sync_note(
        vault_root=vault_root,
        note_path=args.note_path,
        project=args.project,
        memory_root=memory_root,
        slug=args.slug,
    )

    print(f"Synced note to: {output_path}")
    print(f"Updated index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
