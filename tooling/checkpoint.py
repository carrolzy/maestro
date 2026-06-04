#!/usr/bin/env python3
"""Structured agent checkpoints for task resumption.

When an agent works on a task, it records a checkpoint at each step — what it
did, what it produced, what files changed, and what should happen next. If the
agent fails (network, model unavailable, crash), another agent reads the latest
checkpoint and resumes precisely where the first one stopped.

This prevents dead loops (agent B redoing what A already did), memory corruption
(two agents writing conflicting notes), and semantic drift (agent B
misunderstanding the intent).

Checkpoints are stored as append-only JSON files under:
  runtime/task-runs/<project>/<slug>/checkpoints/<seq>-<step>.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    """A single step checkpoint recorded by an agent."""

    agent: str                             # "codex" | "claude"
    step: str                              # "intake" | "implementation" | "verification" | ...
    state: str                             # "completed" | "failed" | "in_progress"
    summary: str                           # human-readable one-liner of what happened
    output: dict[str, Any] | None = None   # structured output from this step
    files_modified: list[str] = field(default_factory=list)  # relative paths
    next_hint: str = ""                    # suggested next step for the resuming agent
    timestamp: str = ""                    # ISO 8601, auto-filled if empty
    session_id: str = ""                   # runtime session id (for hook merge)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _checkpoints_dir(runtime_root: Path, project: str, task_slug: str) -> Path:
    return runtime_root / "task-runs" / project / task_slug / "checkpoints"


def save_checkpoint(
    runtime_root: Path,
    project: str,
    task_slug: str,
    checkpoint: Checkpoint,
) -> Path:
    """Persist a checkpoint. Returns the file path."""
    cdir = _checkpoints_dir(runtime_root, project, task_slug)
    cdir.mkdir(parents=True, exist_ok=True)

    # Determine next sequence number by scanning existing files.
    existing = sorted(cdir.glob("*.json"))
    seq = len(existing) + 1
    filename = f"{seq:03d}-{checkpoint.step}.json"
    path = cdir / filename

    data = {
        "seq": seq,
        "agent": checkpoint.agent,
        "step": checkpoint.step,
        "state": checkpoint.state,
        "summary": checkpoint.summary,
        "output": checkpoint.output,
        "files_modified": checkpoint.files_modified,
        "next_hint": checkpoint.next_hint,
        "timestamp": checkpoint.timestamp,
        "session_id": checkpoint.session_id,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def append_to_session_checkpoint(
    runtime_root: Path,
    project: str,
    task_slug: str,
    *,
    agent: str,
    session_id: str,
    file_modified: str,
) -> Path:
    """Auto-record a file edit into a per-session 'auto-edit' checkpoint.

    Merge rule: if the LATEST checkpoint is an unsealed 'auto-edit' from the same
    session, append the file to it. Otherwise start a new 'auto-edit' checkpoint.
    A checkpoint is "sealed" simply by no longer being the latest — once any
    explicit checkpoint (or a new session's auto-edit) lands after it, it is
    never appended to again. This keeps the hook and explicit checkpoints
    correctly interleaved on the timeline without exploding into one file per
    edit.

    Concurrency-safe: the whole read-modify-write is guarded by a file lock.
    """
    from active_task import _locked  # reuse the same lock primitive

    cdir = _checkpoints_dir(runtime_root, project, task_slug)
    cdir.mkdir(parents=True, exist_ok=True)
    lock_anchor = cdir / ".session.lock"

    with _locked(lock_anchor):
        existing = sorted(cdir.glob("*.json"))
        latest = existing[-1] if existing else None

        if latest is not None:
            try:
                data = json.loads(latest.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
            # Append to the latest only if it's our session's auto-edit.
            if data.get("step") == "auto-edit" and data.get("session_id") == session_id:
                files = list(data.get("files_modified", []))
                if file_modified not in files:
                    files.append(file_modified)
                data["files_modified"] = files
                data["summary"] = f"Auto-recorded {len(files)} file edit(s) this session"
                data["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                latest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return latest

        # Otherwise start a new auto-edit checkpoint.
        seq = len(existing) + 1
        path = cdir / f"{seq:03d}-auto-edit.json"
        payload = {
            "seq": seq,
            "agent": agent,
            "step": "auto-edit",
            "state": "in_progress",
            "summary": "Auto-recorded 1 file edit(s) this session",
            "output": None,
            "files_modified": [file_modified],
            "next_hint": "continue editing or run verification",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": session_id,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path


def load_latest_checkpoint(
    runtime_root: Path,
    project: str,
    task_slug: str,
) -> Checkpoint | None:
    """Load the most recent checkpoint, or None if none exist."""
    cdir = _checkpoints_dir(runtime_root, project, task_slug)
    if not cdir.is_dir():
        return None
    files = sorted(cdir.glob("*.json"))
    if not files:
        return None
    return _file_to_checkpoint(files[-1])


def list_checkpoints(
    runtime_root: Path,
    project: str,
    task_slug: str,
) -> list[Checkpoint]:
    """Return all checkpoints for a task in chronological order."""
    cdir = _checkpoints_dir(runtime_root, project, task_slug)
    if not cdir.is_dir():
        return []
    return [_file_to_checkpoint(f) for f in sorted(cdir.glob("*.json"))]


def build_resume_context(
    runtime_root: Path,
    project: str,
    task_slug: str,
    *,
    system_root: Path | None = None,
) -> dict[str, Any]:
    """Build a complete resume context for a new agent to pick up a task.

    Returns a dict with `can_resume`, `resume_context_pack` (self-contained
    markdown for prompt injection), and structured fields. The calling agent
    can use the structured data or just inject `resume_context_pack` into its
    prompt.
    """
    checkpoints = list_checkpoints(runtime_root, project, task_slug)
    status_path = runtime_root / "task-runs" / project / task_slug / "status.json"

    last_state = "unknown"
    last_agent = "unknown"
    history: list[dict[str, str]] = []
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            last_state = status.get("state", "unknown")
            last_agent = status.get("agent", "unknown")
            history = status.get("history", [])
        except (json.JSONDecodeError, OSError):
            pass

    completed_steps = [
        {
            "agent": cp.agent,
            "step": cp.step,
            "state": cp.state,
            "summary": cp.summary,
            "output": cp.output,
            "timestamp": cp.timestamp,
        }
        for cp in checkpoints
        if cp.state == "completed"
    ]

    all_files: list[str] = []
    for cp in checkpoints:
        all_files.extend(cp.files_modified)
    # dedup preserving order
    seen: set[str] = set()
    files_modified: list[str] = []
    for f in all_files:
        if f not in seen:
            files_modified.append(f)
            seen.add(f)

    latest = checkpoints[-1] if checkpoints else None
    next_hint = latest.next_hint if latest else ""

    can_resume = len(checkpoints) > 0 and last_state not in ("closed", "handed_off")

    # Build the self-contained markdown pack
    pack_lines = [
        "# Task Resume Pack",
        "",
        f"**Project:** {project}",
        f"**Task:** {task_slug}",
        f"**Last agent:** {last_agent}",
        f"**Last state:** {last_state}",
        f"**Can resume:** {can_resume}",
        "",
        "## Agent History",
        "",
    ]
    for entry in history:
        agent_str = entry.get("agent", "?")
        pack_lines.append(f"- `{entry.get('state')}` by **{agent_str}** at {entry.get('updated_at', '?')}")

    pack_lines.extend(["", "## Completed Steps", ""])
    if completed_steps:
        for cs in completed_steps:
            pack_lines.append(f"- **{cs['step']}** ({cs['agent']}): {cs['summary']}")
    else:
        pack_lines.append("- (none)")

    pack_lines.extend(["", "## Files Modified", ""])
    if files_modified:
        for f in files_modified:
            pack_lines.append(f"- `{f}`")
    else:
        pack_lines.append("- (none)")

    pack_lines.extend(["", "## Next Step Hint", "", next_hint or "(no hint — review checkpoints above)"])

    if latest and latest.output:
        pack_lines.extend([
            "",
            "## Latest Output",
            "",
            "```json",
            json.dumps(latest.output, ensure_ascii=False, indent=2),
            "```",
        ])

    pack_lines.extend([
        "",
        "## Instructions for Resuming Agent",
        "",
        f"1. Read the checkpoints above to understand what was already done.",
        f"2. Do NOT redo completed steps — pick up from the latest checkpoint.",
        f"3. The last state was `{last_state}` by **{last_agent}**.",
        f"4. Suggested next step: {next_hint or 'review and decide'}.",
        f"5. After completing your work, call `update_task_run_state` and `writeback_and_sync_memory` as usual.",
        "",
    ])

    return {
        "project": project,
        "task_slug": task_slug,
        "can_resume": can_resume,
        "last_agent": last_agent,
        "last_state": last_state,
        "completed_steps": completed_steps,
        "files_modified": files_modified,
        "next_step_hint": next_hint,
        "recent_checkpoints": [
            {"seq": cp.agent, "step": cp.step, "state": cp.state, "summary": cp.summary, "timestamp": cp.timestamp}
            for cp in (checkpoints[-5:] if checkpoints else [])
        ],
        "agent_history": history,
        "resume_context_pack": "\n".join(pack_lines),
    }


def _file_to_checkpoint(path: Path) -> Checkpoint:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Checkpoint(
        agent=data.get("agent", "unknown"),
        step=data.get("step", "unknown"),
        state=data.get("state", "unknown"),
        summary=data.get("summary", ""),
        output=data.get("output"),
        files_modified=data.get("files_modified", []),
        next_hint=data.get("next_hint", ""),
        timestamp=data.get("timestamp", ""),
        session_id=data.get("session_id", ""),
    )
