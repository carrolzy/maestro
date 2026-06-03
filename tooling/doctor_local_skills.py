#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from local_skills_doctor import assess_local_skills
from runtime_targets import DEFAULT_RUNTIME, known_runtimes, resolve_skills_dest, restart_message


def main(argv: list[str] | None = None, system_root: Path | None = None, stdout_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether repo-local skills are installed and in sync.")
    parser.add_argument("--runtime", default=DEFAULT_RUNTIME, choices=known_runtimes())
    parser.add_argument("--dest", default=None, help="Override skills destination (else AI_EFF_SKILLS_DEST, else runtime default)")
    args = parser.parse_args(argv)

    resolved_system_root = system_root or Path(__file__).resolve().parent.parent
    dest_root = resolve_skills_dest(runtime=args.runtime, dest=args.dest)
    statuses = assess_local_skills(system_root=resolved_system_root, dest_root=dest_root)

    lines = [f"{skill_name}: {status.status} ({status.detail})" for skill_name, status in statuses.items()]
    if any(status.status in {"missing", "drifted", "unmanaged"} for status in statuses.values()):
        lines.append("Run bin/bootstrap-skills.sh to install or repair repo-managed skills.")
        lines.append(restart_message(args.runtime))
        _write_lines(lines, stdout_path=stdout_path)
        return 1

    lines.append("All repo-local skills are installed and in sync.")
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

