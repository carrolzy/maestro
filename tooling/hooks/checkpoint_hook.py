#!/usr/bin/env python3
"""PostToolUse hook — auto-record a checkpoint after every file edit.

Wired into Claude Code (and other runtimes) so checkpoints are FORCED, not left
to the model's discretion. After each Edit/Write/MultiEdit, this script:

  1. Reads the hook payload from stdin (tool_name, tool_input.file_path, session_id)
  2. Reads the active-task pointer — if none, exits silently (no active task = nothing to record)
  3. Appends the edited file to a per-session 'auto-edit' checkpoint

It NEVER blocks the edit: it always exits 0, even on error. A broken hook must
not break the user's workflow.

Reads runtime root from AI_EFF_RUNTIME_ROOT, else <cwd>/runtime.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make tooling/ importable regardless of how the hook is invoked.
_TOOLING = Path(__file__).resolve().parent.parent
if str(_TOOLING) not in sys.path:
    sys.path.insert(0, str(_TOOLING))

_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def main() -> int:
    # 1. Parse stdin (never raise — a malformed payload just means "skip").
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in _EDIT_TOOLS:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0

    session_id = payload.get("session_id", "") or "default"

    try:
        from active_task import get_active_task, resolve_runtime_root
        from checkpoint import append_to_session_checkpoint

        runtime_root = resolve_runtime_root()
        active = get_active_task(runtime_root)
        if not active:
            # No active task → nothing to attribute this edit to. Silent.
            return 0

        # Record the edit relative to cwd when possible (cleaner paths).
        rel = _relativize(file_path, payload.get("cwd"))

        append_to_session_checkpoint(
            runtime_root,
            active["project"],
            active["task_slug"],
            agent=active.get("agent", "unknown"),
            session_id=session_id,
            file_modified=rel,
        )
    except Exception:
        # Any failure: stay invisible. Do not block the edit.
        return 0

    return 0


def _relativize(file_path: str, cwd: str | None) -> str:
    if not cwd:
        return file_path
    try:
        return str(Path(file_path).resolve().relative_to(Path(cwd).resolve()))
    except (ValueError, OSError):
        return file_path


if __name__ == "__main__":
    sys.exit(main())
