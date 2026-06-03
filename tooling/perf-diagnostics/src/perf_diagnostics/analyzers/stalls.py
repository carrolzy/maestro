from __future__ import annotations


def analyze_stalls(task_events: list[dict[str, object]], threshold_ms: float = 50.0) -> dict[str, object]:
    long_tasks = [event for event in task_events if float(event["duration_ms"]) >= threshold_ms]
    stall_windows = []
    for event in long_tasks:
        stall_windows.append(
            {
                "start_ms": event["start_ms"],
                "end_ms": event["end_ms"],
                "duration_ms": event["duration_ms"],
                "script": event["script"],
                "stack": event["stack"],
            }
        )

    total_ms = round(sum(float(event["duration_ms"]) for event in long_tasks), 3)
    max_ms = round(max((float(event["duration_ms"]) for event in long_tasks), default=0.0), 3)
    return {
        "long_task_count": len(long_tasks),
        "long_task_total_ms": total_ms,
        "max_blocking_task_ms": max_ms,
        "stall_windows": stall_windows,
        "user_visible_windows": stall_windows,
    }
