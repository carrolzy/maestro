#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


GOVERNANCE_TIERS = {"L0", "L1", "L2", "L3"}
DOCUMENTATION_STATUSES = {"updated", "not_needed"}


def _validated_documentation_impact(
    *,
    state: str,
    governance_tier: str | None,
    documentation_impact: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if governance_tier is not None and governance_tier not in GOVERNANCE_TIERS:
        raise ValueError("governance_tier must be one of L0, L1, L2, L3")

    if state == "closed" and governance_tier is None:
        raise ValueError("governance_tier is required when closing a task")
    if state == "closed" and documentation_impact is None:
        raise ValueError("documentation_impact is required when closing a task")
    if documentation_impact is None:
        return None
    if not isinstance(documentation_impact, dict):
        raise ValueError("documentation_impact must be an object")

    status = documentation_impact.get("status")
    if status not in DOCUMENTATION_STATUSES:
        raise ValueError("documentation_impact.status must be updated or not_needed")
    reason = documentation_impact.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("documentation_impact.reason must be a non-empty string")

    files = documentation_impact.get("files", [])
    if not isinstance(files, list) or any(not isinstance(item, str) or not item.strip() for item in files):
        raise ValueError("documentation_impact.files must be an array of non-empty strings")
    if status == "updated" and not files:
        raise ValueError("documentation_impact.files is required when status is updated")

    return {
        "status": status,
        "files": files,
        "reason": reason.strip(),
    }


def update_task_run_state(
    *,
    runtime_root: Path,
    project: str,
    task_slug: str,
    state: str,
    agent: str | None = None,
    governance_tier: str | None = None,
    documentation_impact: dict[str, Any] | None = None,
) -> Path:
    validated_documentation_impact = _validated_documentation_impact(
        state=state,
        governance_tier=governance_tier,
        documentation_impact=documentation_impact,
    )
    target_dir = runtime_root / "task-runs" / project / task_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "status.json"
    history: list[dict[str, Any]] = []
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
    if governance_tier:
        entry["governance_tier"] = governance_tier
    if validated_documentation_impact:
        entry["documentation_impact"] = validated_documentation_impact
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
    if governance_tier:
        payload["governance_tier"] = governance_tier
    if validated_documentation_impact:
        payload["documentation_impact"] = validated_documentation_impact

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path
