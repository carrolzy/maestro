from __future__ import annotations

from collections import defaultdict


KEYWORD_RULES = [
    ("patch", ("patch",)),
    ("diff", ("diff",)),
    ("flushSchedulerQueue", ("flushschedulerqueue",)),
    ("cloneWithData", ("clonewithdata",)),
    ("setData", ("setdata",)),
    ("destroy", ("destroy", "detached", "disconnect")),
    ("observer", ("observer",)),
    ("request", ("request", "callback", "merge")),
    ("scroll", ("scroll",)),
]


def analyze_hotspots(task_events: list[dict[str, object]]) -> dict[str, object]:
    script_totals: dict[str, float] = defaultdict(float)
    keyword_totals: dict[str, float] = defaultdict(float)
    stack_totals: dict[str, float] = defaultdict(float)

    for event in task_events:
        duration = float(event["duration_ms"])
        script = str(event["script"])
        stack = str(event["stack"])
        script_totals[script] += duration
        stack_totals[stack] += duration
        for keyword, aliases in KEYWORD_RULES:
            if any(alias in stack.lower() for alias in aliases):
                keyword_totals[keyword] += duration

    top_scripts = _sorted_entries(script_totals, "script")
    top_keywords = _sorted_entries(keyword_totals, "keyword", priority=["patch", "diff", "flushSchedulerQueue", "cloneWithData"])
    top_stacks = _sorted_entries(stack_totals, "stack")
    return {
        "top_scripts": top_scripts,
        "top_keywords": top_keywords,
        "top_stacks": top_stacks,
    }


def _sorted_entries(
    values: dict[str, float],
    field_name: str,
    priority: list[str] | None = None,
) -> list[dict[str, object]]:
    priority_map = {value: index for index, value in enumerate(priority or [])}
    ordered = sorted(
        values.items(),
        key=lambda item: (
            priority_map.get(item[0], len(priority_map)),
            -item[1],
            item[0],
        ),
    )
    return [
        {field_name: key, "total_duration_ms": round(value, 3)}
        for key, value in ordered
    ]
