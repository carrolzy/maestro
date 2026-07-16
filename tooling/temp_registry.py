#!/usr/bin/env python3
"""Temp-file registry — track short-lived helper files left in business repos.

Agents produce throwaway artifacts (test.js, *.cjs probes, debug scripts) while
working. Most belong in the central scratch area (`runtime/scratch/`), but some
must sit inside the business repo to be picked up by its tooling. Those are
registered here with a TTL so `artifact_gc` can reclaim them later instead of
letting them pile up in the project forever.

Safety model: the registry only *records*; deletion happens exclusively in
`artifact_gc clean`, which additionally refuses to touch git-tracked files.

Registry lives at `runtime/temp-files.json`, guarded by the same fcntl lock
pattern as the active-task pointer.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from active_task import _locked

DEFAULT_TTL_DAYS = 30

# Filename patterns treated as temp artifacts by auto-registration.
# Deliberately conservative: only obvious throwaway shapes.
TEMP_NAME_PATTERNS = (
    "tmp-*",
    "temp-*",
    "*-debug.*",
    "debug-*",
    "*.test.cjs",
    "*.test.mjs",
    "scratch-*",
    "verify-*.js",
    "verify-*.cjs",
    "verify-*.py",
)


def _registry_path(runtime_root: Path) -> Path:
    return runtime_root / "temp-files.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(runtime_root: Path) -> list[dict[str, Any]]:
    path = _registry_path(runtime_root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, list) else []


def _save(runtime_root: Path, entries: list[dict[str, Any]]) -> Path:
    path = _registry_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": entries}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def matches_temp_pattern(filename: str) -> bool:
    """True if a bare filename looks like a throwaway artifact."""
    from fnmatch import fnmatch

    return any(fnmatch(filename, pattern) for pattern in TEMP_NAME_PATTERNS)


def register_temp_file(
    runtime_root: Path,
    *,
    file_path: str,
    project: str,
    task_slug: str,
    ttl_days: int = DEFAULT_TTL_DAYS,
    reason: str = "",
) -> dict[str, Any]:
    """Register (or refresh) a temp file. Absolute path required.

    Re-registering an existing path refreshes its expiry from now.
    """
    abs_path = str(Path(file_path).expanduser().resolve())
    now = _now()
    entry = {
        "path": abs_path,
        "project": project,
        "task_slug": task_slug,
        "reason": reason,
        "registered_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(days=ttl_days)).isoformat(timespec="seconds"),
    }
    reg_path = _registry_path(runtime_root)
    with _locked(reg_path):
        entries = _load(runtime_root)
        entries = [e for e in entries if e.get("path") != abs_path]
        entries.append(entry)
        _save(runtime_root, entries)
    return entry


def list_temp_files(runtime_root: Path, *, project: str | None = None) -> list[dict[str, Any]]:
    entries = _load(runtime_root)
    if project:
        entries = [e for e in entries if e.get("project") == project]
    return entries


def expired_temp_files(runtime_root: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Entries whose expiry has passed. Entries with unparsable dates are skipped."""
    current = now or _now()
    expired: list[dict[str, Any]] = []
    for entry in _load(runtime_root):
        try:
            expires = datetime.fromisoformat(entry["expires_at"])
        except (KeyError, ValueError):
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= current:
            expired.append(entry)
    return expired


def refresh_task_temp_files(
    runtime_root: Path,
    *,
    project: str,
    task_slug: str,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> int:
    """Restart the TTL clock for every temp file of a task (e.g. at task close,
    so the post-release verification window starts from the close date, not the
    creation date). Returns the number of refreshed entries."""
    now = _now()
    new_expiry = (now + timedelta(days=ttl_days)).isoformat(timespec="seconds")
    reg_path = _registry_path(runtime_root)
    refreshed = 0
    with _locked(reg_path):
        entries = _load(runtime_root)
        for entry in entries:
            if entry.get("project") == project and entry.get("task_slug") == task_slug:
                entry["expires_at"] = new_expiry
                refreshed += 1
        if refreshed:
            _save(runtime_root, entries)
    return refreshed


def remove_entries(runtime_root: Path, paths: list[str]) -> int:
    """Drop registry entries by absolute path (after their files were deleted)."""
    targets = {str(Path(p).expanduser().resolve()) for p in paths}
    reg_path = _registry_path(runtime_root)
    with _locked(reg_path):
        entries = _load(runtime_root)
        kept = [e for e in entries if e.get("path") not in targets]
        removed = len(entries) - len(kept)
        if removed:
            _save(runtime_root, kept)
    return removed
