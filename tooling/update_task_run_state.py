#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


def update_task_run_state(
    *,
    runtime_root: Path,
    project: str,
    task_slug: str,
    state: str,
    agent: str | None = None,
) -> Path:
    target_dir = runtime_root / "task-runs" / project / task_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "status.json"
    history: list[dict[str, str]] = []
    existing_agent: str | None = None
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            history = list(existing.get("history", []))
            existing_agent = existing.get("agent")
        except json.JSONDecodeError:
            history = []

    updated_at = datetime.now().isoformat(timespec="seconds")
    entry: dict[str, str] = {
        "state": state,
        "updated_at": updated_at,
    }
    if agent:
        entry["agent"] = agent
    history.append(entry)

    payload: dict[str, Any] = {
        "project": project,
        "task_slug": task_slug,
        "state": state,
        "updated_at": updated_at,
        "history": history,
    }
    # Carry forward agent if not explicitly set (backward-compat: old files)
    effective_agent = agent or existing_agent
    if effective_agent:
        payload["agent"] = effective_agent

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path
