#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from local_skill_installer import MARKER_FILENAME, install_local_skill, list_local_skills


@dataclass(frozen=True)
class SkillInstallStatus:
    skill_name: str
    status: str
    detail: str


def assess_local_skills(*, system_root: Path, dest_root: Path) -> dict[str, SkillInstallStatus]:
    statuses: dict[str, SkillInstallStatus] = {}
    for skill_name in list_local_skills(system_root=system_root):
        source_dir = system_root / "skills" / skill_name
        target_dir = dest_root / skill_name
        if not target_dir.exists():
            statuses[skill_name] = SkillInstallStatus(skill_name, "missing", "skill is not installed")
            continue

        marker_path = target_dir / MARKER_FILENAME
        if not marker_path.exists():
            statuses[skill_name] = SkillInstallStatus(skill_name, "unmanaged", "existing directory is not repo-managed")
            continue

        marker_source = marker_path.read_text(encoding="utf-8").strip()
        expected_source = str(source_dir.resolve())
        if marker_source != expected_source:
            statuses[skill_name] = SkillInstallStatus(skill_name, "unmanaged", "managed by a different source path")
            continue

        if _directories_match(source_dir=source_dir, target_dir=target_dir):
            statuses[skill_name] = SkillInstallStatus(skill_name, "installed", "installed and in sync")
        else:
            statuses[skill_name] = SkillInstallStatus(skill_name, "drifted", "installed copy differs from repo source")
    return statuses


def bootstrap_local_skills(*, system_root: Path, dest_root: Path) -> dict[str, str]:
    results: dict[str, str] = {}
    statuses = assess_local_skills(system_root=system_root, dest_root=dest_root)
    for skill_name, status in statuses.items():
        if status.status == "installed":
            results[skill_name] = "ok"
            continue
        if status.status == "unmanaged":
            results[skill_name] = "skipped-unmanaged"
            continue

        install_local_skill(system_root=system_root, dest_root=dest_root, skill_name=skill_name)
        if status.status == "missing":
            results[skill_name] = "installed"
        else:
            results[skill_name] = "reinstalled"
    return results


def _directories_match(*, source_dir: Path, target_dir: Path) -> bool:
    source_files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    target_files = sorted(
        path for path in target_dir.rglob("*") if path.is_file() and path.name != MARKER_FILENAME
    )

    source_relative = [path.relative_to(source_dir) for path in source_files]
    target_relative = [path.relative_to(target_dir) for path in target_files]
    if source_relative != target_relative:
        return False

    for relative_path in source_relative:
        if (source_dir / relative_path).read_bytes() != (target_dir / relative_path).read_bytes():
            return False
    return True
