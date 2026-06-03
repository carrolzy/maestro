from __future__ import annotations

import json
from pathlib import Path


def load_trace(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON: {path}") from exc

    if isinstance(payload, list):
        return {"traceEvents": payload}

    if not isinstance(payload, dict):
        raise ValueError("Trace JSON must be an object or a top-level traceEvents array.")

    trace_events = payload.get("traceEvents")
    if not isinstance(trace_events, list):
        raise ValueError("Trace JSON must contain a traceEvents array.")
    return payload
