#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from local_skills_doctor import bootstrap_local_skills
from runtime_targets import DEFAULT_RUNTIME, known_runtimes, resolve_skills_dest, restart_message


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install or repair repo-local skills in an agent runtime's skills directory."
    )
    parser.add_argument("--runtime", default=DEFAULT_RUNTIME, choices=known_runtimes())
    parser.add_argument("--dest", default=None, help="Override skills destination (else AI_EFF_SKILLS_DEST, else runtime default)")
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    dest_root = resolve_skills_dest(runtime=args.runtime, dest=args.dest)
    results = bootstrap_local_skills(system_root=resolved_system_root, dest_root=dest_root)

    lines = [f"{skill_name}: {result}" for skill_name, result in results.items()]
    lines.append(restart_message(args.runtime))
    _write_lines(lines, stdout_path=stdout_path)
    return 0


def _write_lines(lines: list[str], *, stdout_path: Path | None) -> None:
    text = "".join(f"{line}\n" for line in lines)
    if stdout_path is not None:
        stdout_path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
