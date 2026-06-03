#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

MARKER_FILENAME = ".ai-efficiency-system-source"


def list_local_skills(*, system_root: Path) -> list[str]:
    skills_root = system_root / "skills"
    if not skills_root.exists():
        return []

    skill_names: list[str] = []
    for child in skills_root.iterdir():
        if not child.is_dir():
            continue
        if not (child / "SKILL.md").exists():
            continue
        skill_names.append(child.name)
    return sorted(skill_names)


def install_all_local_skills(*, system_root: Path, dest_root: Path) -> list[Path]:
    installed_dirs: list[Path] = []
    for skill_name in list_local_skills(system_root=system_root):
        installed_dirs.append(
            install_local_skill(
                system_root=system_root,
                dest_root=dest_root,
                skill_name=skill_name,
            )
        )
    return installed_dirs


def install_local_skill(
    *,
    system_root: Path,
    dest_root: Path,
    skill_name: str,
    takeover_unmanaged: bool = False,
) -> Path:
    source_dir = system_root / "skills" / skill_name
    if not (source_dir / "SKILL.md").exists():
        raise ValueError(f"Unknown local skill: {skill_name}")

    target_dir = dest_root / skill_name
    if target_dir.exists():
        if takeover_unmanaged:
            _assert_takeover_allowed(target_dir=target_dir)
        else:
            _assert_managed_target(target_dir=target_dir, source_dir=source_dir)
        shutil.rmtree(target_dir)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)
    (target_dir / MARKER_FILENAME).write_text(str(source_dir.resolve()) + "\n", encoding="utf-8")
    return target_dir


def _assert_managed_target(*, target_dir: Path, source_dir: Path) -> None:
    marker_path = target_dir / MARKER_FILENAME
    if not marker_path.exists():
        raise FileExistsError(f"{target_dir} already exists and is not managed by this installer")

    marker_source = marker_path.read_text(encoding="utf-8").strip()
    expected_source = str(source_dir.resolve())
    if marker_source != expected_source:
        raise FileExistsError(
            f"{target_dir} already exists and is not managed by this installer for source {expected_source}"
        )


def _assert_takeover_allowed(*, target_dir: Path) -> None:
    if not target_dir.exists():
        return
    if not target_dir.is_dir():
        raise FileExistsError(f"{target_dir} exists and is not a directory")
