#!/usr/bin/env python3
"""PostToolUse hook — auto-record a checkpoint after every file edit.

Runtime-agnostic: works for both Claude Code and Codex CLI. Both runtimes fire
a PostToolUse hook with a JSON payload on stdin, but they differ in tool names
and field layout, so this script matches loosely:

  - Claude:  tool_name "Edit"/"Write"/"MultiEdit", path in tool_input.file_path
  - Codex:   tool_name "edit_file"/"write_file"/"apply_patch" (etc.), path in
             tool_input.path or embedded in an apply_patch body

It NEVER blocks the edit: always exits 0, even on error. A broken hook must not
break the user's workflow.

Checkpoints are written to the Maestro repo's runtime/ (inferred from this
script's location), so edits made from inside a business project still land in
the central Maestro task-run store.

Set AI_EFF_HOOK_DEBUG=1 to also append the raw payload to
runtime/hook-debug.jsonl — useful for discovering a new runtime's exact schema.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Make tooling/ importable regardless of how the hook is invoked.
_TOOLING = Path(__file__).resolve().parent.parent
if str(_TOOLING) not in sys.path:
    sys.path.insert(0, str(_TOOLING))

# Edit-intent tokens (case-insensitive substring match on the tool name).
_EDIT_TOKENS = ("edit", "write", "patch", "apply", "create", "update", "multiedit", "notebook")
# Tools that clearly are NOT edits, even if a token sneaks in.
_NON_EDIT = ("read", "search", "grep", "glob", "list", "view", "fetch")

_PATH_KEYS = ("file_path", "path", "notebook_path", "filename", "target_file", "filePath")


def _is_edit_tool(name: str) -> bool:
    low = name.lower()
    if any(tok in low for tok in _NON_EDIT) and "patch" not in low and "write" not in low:
        return False
    return any(tok in low for tok in _EDIT_TOKENS)


def _parse_patch_path(text: str) -> str:
    """Best-effort: pull a file path out of an apply_patch / unified-diff body."""
    if not text:
        return ""
    # Codex apply_patch: '*** Update File: path' / '*** Add File: path'
    m = re.search(r"\*\*\*\s+(?:Update|Add|Delete|Move)\s+File:\s+(.+)", text)
    if m:
        return m.group(1).strip()
    # Unified diff: '+++ b/path'
    m = re.search(r"^\+\+\+\s+b/(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return ""


def _extract_path(tool_input: dict) -> str:
    for k in _PATH_KEYS:
        v = tool_input.get(k)
        if isinstance(v, str) and v:
            return v
    # apply_patch style: path embedded in the patch text.
    # Codex reports the apply_patch body in tool_input.command (per the Codex
    # hooks schema); other runtimes use input/patch/diff/content.
    for k in ("command", "input", "patch", "diff", "content"):
        v = tool_input.get(k)
        if isinstance(v, str) and v:
            p = _parse_patch_path(v)
            if p:
                return p
    return ""


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0

    # Debug bypass: capture the raw payload to discover a runtime's schema.
    import os
    if os.environ.get("AI_EFF_HOOK_DEBUG") == "1":
        try:
            from active_task import resolve_runtime_root
            dbg = resolve_runtime_root()
            dbg.mkdir(parents=True, exist_ok=True)
            with open(dbg / "hook-debug.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    tool_name = payload.get("tool_name", "") or payload.get("tool", "")
    if not isinstance(tool_name, str) or not _is_edit_tool(tool_name):
        return 0

    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("arguments") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    file_path = _extract_path(tool_input)
    if not file_path:
        return 0

    session_id = payload.get("session_id", "") or payload.get("sessionId", "") or "default"

    try:
        from active_task import get_active_task, resolve_runtime_root
        from checkpoint import append_to_session_checkpoint

        runtime_root = resolve_runtime_root()
        active = get_active_task(runtime_root)
        if not active:
            return 0  # no active task → nothing to attribute this edit to

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
        return 0  # stay invisible; never block the edit

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
