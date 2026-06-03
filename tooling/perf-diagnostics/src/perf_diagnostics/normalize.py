from __future__ import annotations

from collections import Counter


def normalize_trace(trace: dict[str, object]) -> dict[str, object]:
    trace_events = trace.get("traceEvents", [])
    task_events = []
    category_counts = Counter()
    min_start = None
    max_end = None
    has_script_name = False
    has_stack = False

    for event in trace_events:
        if not isinstance(event, dict):
            continue
        category = str(event.get("cat") or "unknown")
        category_counts[category] += 1
        start_us = _coerce_float(event.get("ts"))
        duration_us = _coerce_float(event.get("dur"))
        if start_us is None:
            continue
        end_us = start_us + max(duration_us or 0.0, 0.0)
        min_start = start_us if min_start is None else min(min_start, start_us)
        max_end = end_us if max_end is None else max(max_end, end_us)

        if duration_us is None or duration_us <= 0:
            continue
        data = ((event.get("args") or {}).get("data") or {}) if isinstance(event.get("args"), dict) else {}
        script = str(data.get("scriptName") or event.get("scriptName") or "unknown")
        stack = str(data.get("stack") or data.get("callFrame") or event.get("name") or "")
        has_script_name = has_script_name or script != "unknown"
        has_stack = has_stack or bool(stack)
        task_events.append(
            {
                "name": str(event.get("name") or "unknown"),
                "category": category,
                "start_us": start_us,
                "end_us": end_us,
                "start_ms": round(start_us / 1000.0, 3),
                "end_ms": round(end_us / 1000.0, 3),
                "duration_ms": round(duration_us / 1000.0, 3),
                "script": script,
                "stack": stack,
            }
        )

    time_span_ms = 0.0
    if min_start is not None and max_end is not None:
        time_span_ms = round((max_end - min_start) / 1000.0, 3)

    return {
        "trace_overview": {
            "event_count": len(trace_events),
            "task_event_count": len(task_events),
            "time_span_ms": time_span_ms,
            "top_categories": [
                {"category": category, "count": count}
                for category, count in category_counts.most_common(5)
            ],
            "has_script_names": has_script_name,
            "has_stack_strings": has_stack,
        },
        "task_events": task_events,
    }


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
