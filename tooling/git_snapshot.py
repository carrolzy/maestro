#!/usr/bin/env python3
"""Git-based change snapshot — capture which files a session touched.

Codex (as of 0.137) does not reliably run PostToolUse hooks, so the
"edit a file → auto-checkpoint" path is dead on that runtime. Instead we let an
agent (or a session-end step) ask git directly: "what changed in this repo?" and
record those paths as a checkpoint. This is runtime-independent — it works the
same whether the edits came from Codex, Claude, or a human.

Pure stdlib + the `git` CLI. No third-party deps.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(repo_root: Path, *args: str) -> str:
    """Run a git command in repo_root, returning stdout. Empty string on error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def is_git_repo(repo_root: Path) -> bool:
    return _run_git(repo_root, "rev-parse", "--is-inside-work-tree").strip() == "true"


def git_changed_files(repo_root: Path) -> list[str]:
    """Return repo-relative paths of changed files (staged + unstaged + untracked).

    Uses `git status --porcelain` so it covers modified, added, renamed, copied,
    and untracked files in one pass. Deleted files are skipped — a checkpoint of
    "what to resume" cares about files that still exist. Paths are repo-relative
    and de-duplicated, preserving first-seen order.
    """
    out = _run_git(repo_root, "status", "--porcelain")
    if not out:
        return []

    seen: set[str] = set()
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # Porcelain v1: XY<space>path  (rename/copy: "XY old -> new")
        status = line[:2]
        rest = line[3:]
        if "D" in status and "R" not in status:
            continue  # pure deletion — nothing to resume into
        path = rest.split(" -> ", 1)[1] if " -> " in rest else rest
        path = path.strip().strip('"')
        if path and path not in seen:
            seen.add(path)
            files.append(path)
    return files
