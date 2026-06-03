#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from local_skill_installer import install_all_local_skills, install_local_skill, list_local_skills
from runtime_targets import DEFAULT_RUNTIME, known_runtimes, resolve_skills_dest


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install repo-local skills into an agent runtime's skills directory.")
    parser.add_argument("skill_names", nargs="*")
    parser.add_argument("--all", action="store_true", dest="install_all")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--runtime", default=DEFAULT_RUNTIME, choices=known_runtimes())
    parser.add_argument("--dest", default=None, help="Override skills destination (else AI_EFF_SKILLS_DEST, else runtime default)")
    parser.add_argument("--takeover", action="store_true", help="Allow explicit takeover of an existing unmanaged skill directory.")
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    dest_root = resolve_skills_dest(runtime=args.runtime, dest=args.dest)

    if args.list:
        _write_lines(list_local_skills(system_root=resolved_system_root), stdout_path=stdout_path)
        return 0

    if args.install_all:
        if args.skill_names:
            raise SystemExit("--all cannot be combined with explicit skill names")
        installed_dirs = install_all_local_skills(system_root=resolved_system_root, dest_root=dest_root)
        _write_lines([str(path) for path in installed_dirs], stdout_path=stdout_path)
        return 0

    if not args.skill_names:
        raise SystemExit("Specify one or more skill names, or use --all / --list")

    installed_dirs = [
        install_local_skill(
            system_root=resolved_system_root,
            dest_root=dest_root,
            skill_name=skill_name,
            takeover_unmanaged=args.takeover,
        )
        for skill_name in args.skill_names
    ]
    _write_lines([str(path) for path in installed_dirs], stdout_path=stdout_path)
    return 0


def _write_lines(lines: list[str], *, stdout_path: Path | None) -> None:
    text = "".join(f"{line}\n" for line in lines)
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
