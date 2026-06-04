#!/usr/bin/env python3
"""Active-task pointer — bridges file edits to the task they belong to.

A PostToolUse hook knows *which file* was edited, but not *which task* that edit
belongs to. This module maintains a small pointer (`runtime/active-task.json`)
that an agent sets when it starts working. The hook reads it to attribute
auto-recorded checkpoints to the right task.

Writes are guarded by a cross-process file lock (fcntl) so the hook and the MCP
server never corrupt the pointer when they run concurrently.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ENV_RUNTIME_ROOT = "AI_EFF_RUNTIME_ROOT"


def resolve_runtime_root(explicit: Path | None = None) -> Path:
    """Resolve the runtime root.

    Priority:
      1. explicit arg
      2. AI_EFF_RUNTIME_ROOT env var
      3. Maestro repo root inferred from THIS module's location (tooling/ ->
         repo root -> runtime/). This is correct even when invoked as a hook
         from inside a *business project* directory, where cwd is the business
         project, not the Maestro repo.
      4. cwd/runtime (last-resort fallback)
    """
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get(ENV_RUNTIME_ROOT)
    if env:
        return Path(env)
    # active_task.py lives in <repo>/tooling/, so parent.parent is the repo root.
    repo_root = Path(__file__).resolve().parent.parent
    candidate = repo_root / "runtime"
    if candidate.exists() or (repo_root / "tooling").is_dir():
        return candidate
    return Path.cwd() / "runtime"


def _pointer_path(runtime_root: Path) -> Path:
    return runtime_root / "active-task.json"


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Cross-process exclusive lock via a sidecar .lock file (fcntl)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        try:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            # Windows or lock-unsupported FS: degrade gracefully (no lock).
            pass
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        lock_file.close()


def set_active_task(
    runtime_root: Path,
    project: str,
    task_slug: str,
    agent: str,
) -> Path:
    """Set the active-task pointer. Returns the pointer path."""
    path = _pointer_path(runtime_root)
    with _locked(path):
        payload: dict[str, Any] = {
            "project": project,
            "task_slug": task_slug,
            "agent": agent,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def get_active_task(runtime_root: Path) -> dict[str, Any] | None:
    """Read the active-task pointer, or None if unset/invalid."""
    path = _pointer_path(runtime_root)
    if not path.exists():
        return None
    try:
        with _locked(path):
            data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("project") and data.get("task_slug"):
            return data
    except (json.JSONDecodeError, OSError):
        return None
    return None


def clear_active_task(runtime_root: Path) -> bool:
    """Clear the active-task pointer. Returns True if a pointer was removed."""
    path = _pointer_path(runtime_root)
    if not path.exists():
        return False
    with _locked(path):
        try:
            path.unlink()
            return True
        except OSError:
            return False
